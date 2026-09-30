/*--------------------------------------------------------------*
  Copyright (C) 2006-2025 OpenSim Ltd.

  This file is distributed WITHOUT ANY WARRANTY. See the file
  'License' for details on this and other legal matters.
*--------------------------------------------------------------*/
package org.omnetpp.common.locking;

import java.lang.Thread.State;
import java.lang.management.LockInfo;
import java.lang.management.ManagementFactory;
import java.lang.management.MonitorInfo;
import java.lang.management.ThreadInfo;
import java.lang.management.ThreadMXBean;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;

import org.apache.commons.lang3.ArrayUtils;
import org.eclipse.core.runtime.ILog;
import org.eclipse.jface.dialogs.MessageDialog;
import org.eclipse.swt.widgets.Display;
import org.omnetpp.common.CommonCorePlugin;
import org.omnetpp.common.Debug;

/**
 * Implements a deadlock detection mechanism.
 *
 * There are two kinds of deadlocks in the IDE:
 * 1. Between threads
 * 2. UI lockup (typically syncExec)
 *
 * The first kind of deadlock is created between two jobs using two locks, one for the workspace
 * and another one for the e.g. NED resources. The detector checks for deadlocks periodically
 * and the resolver interrupts the locking mechanism. Only locks acquired by lockInterruptibly()
 * can be interrupted this way.
 *
 * Eclipse itself does not detect deadlocks automatically.
 *
 * The second kind of deadlock goes e.g. like this: A job calls Display.syncExec()
 * (which submits a lambda into the UI event queue, and waits until it is
 * processed). But for some reason, the submitted lambda (or a non-yet
 * executed lambda submitted by an earlier asyncExec call) needs to lock a
 * resource that is currently held by the job --> UI locks up.
 *
 * "Normal" deadlocks are detected by threadMxBean.findDeadlockedThreads().
 * UI deadlocks are detected by checking for the UI thread being blocked
 * for a long time (e.g. 10s).
 *
 * Resolution is to interrupt. But this is only possible if the lock was acquired
 * with lockInterruptibly(). So we need to change the locking mechanism
 * wherever possible.
 */
///TODO deadlock examples, and way to activate them
public class DeadlockDetector implements Runnable {
    public static boolean debug = Debug.isChannelEnabled("deadlockdetector");

    // Deadlock checking frequency
    private static final long CHECK_PERIOD_MS = 2000;

    // Threshold for UI thread blocking time in milliseconds before considering it a deadlock
    private static final long UI_THREAD_BLOCKING_THRESHOLD_MS = 10000; // 10 seconds

    private final ScheduledExecutorService scheduler;
    private final ThreadMXBean threadMxBean;
    private final ILog log;
    private boolean dialogVisible = false;

    public DeadlockDetector() {
        this.threadMxBean = ManagementFactory.getThreadMXBean();
        this.log = CommonCorePlugin.getDefault().getLog();

        // Enable thread contention monitoring if supported
        if (threadMxBean.isThreadContentionMonitoringSupported()) {
            threadMxBean.setThreadContentionMonitoringEnabled(true);
            log.error("Thread contention monitoring enabled");
        }
        else {
            log.error("Thread contention monitoring not supported on this JVM");
        }

        this.scheduler = Executors.newSingleThreadScheduledExecutor(new ThreadFactory() {
            @Override
            public Thread newThread(Runnable r) {
                Thread t = new Thread(r, "DeadlockDetector");
                t.setDaemon(true);
                return t;
            }
        });
    }

    /**
     * Start periodic deadlock checking.
     */
    public void start() {
        // initial delay == CHECK_PERIOD_MS, so first check happens after one CHECK_PERIOD_MS elapses
        scheduler.scheduleAtFixedRate(this, CHECK_PERIOD_MS, CHECK_PERIOD_MS, TimeUnit.MILLISECONDS);
        if (debug)
            Debug.println("Deadlock detection started, period is " + CHECK_PERIOD_MS + "ms");
    }

    /**
     * Stop periodic deadlock checking.
     */
    public void stop() {
        scheduler.shutdownNow();
    }


    @Override
    public void run() {
        long[] deadlockedThreadIds = threadMxBean.findDeadlockedThreads();  // runtime cost: usually 1-2ms
        long uiThreadId = Display.getDefault().getThread().getId();
        if (deadlockedThreadIds != null && deadlockedThreadIds.length > 0 && !ArrayUtils.contains(deadlockedThreadIds, uiThreadId)) {
            ThreadInfo[] infos = threadMxBean.getThreadInfo(deadlockedThreadIds, true, true);
            StringBuilder logMessage = new StringBuilder("=== DEADLOCK DETECTED ===\n");

            // Add deadlock cycle analysis
            String deadlockCycle = analyzeDeadlockCycle(infos);
            if (deadlockCycle != null) {
                logMessage.append(deadlockCycle).append("\n");
            }

            // Add detailed thread information
            for (ThreadInfo ti : infos)
                logMessage.append(buildThreadInfoString(ti)).append("\n");
            log.error(logMessage.toString());

            Deadlock deadlock = new Deadlock();
            deadlock.infos = infos;
            handleDeadlock(deadlock);
        }
        else {
            Thread uiThread = Display.getDefault().getThread();
            State uiThreadState = uiThread.getState();

            if (debug)
                Debug.println("UI thread state: " + uiThreadState);

            if (uiThreadState == Thread.State.BLOCKED || uiThreadState == Thread.State.WAITING) {
                ThreadInfo info = threadMxBean.getThreadInfo(uiThread.getId(), 100);

                // Get blocked and waited times if contention monitoring is enabled
                long blockedTime = threadMxBean.isThreadContentionMonitoringEnabled() ? info.getBlockedTime() : -1;
                long waitedTime = threadMxBean.isThreadContentionMonitoringEnabled() ? info.getWaitedTime() : -1;

                // Log the current state for diagnostic purposes if requested
                if (debug)
                    Debug.println("UI thread state: " + uiThreadState +
                                 ", blocked time: " + (blockedTime >= 0 ? blockedTime + "ms" : "unknown") +
                                 ", waited time: " + (waitedTime >= 0 ? waitedTime + "ms" : "unknown"));

                // Only consider it a deadlock if the thread has been blocked/waiting for longer than the threshold
                if (blockedTime > UI_THREAD_BLOCKING_THRESHOLD_MS || waitedTime > UI_THREAD_BLOCKING_THRESHOLD_MS) {
                    StringBuilder logMessage = new StringBuilder("=== LASTING UI THREAD BLOCKING DETECTED, POTENTIAL DEADLOCK ===\n");
                    logMessage.append("UI thread state: ").append(uiThreadState).append("\n");
                    logMessage.append("Blocked time: ").append(blockedTime).append("ms, Waited time: ").append(waitedTime).append("ms\n");
                    logMessage.append(buildThreadInfoString(info));
                    log.error(logMessage.toString());


                    ThreadInfo[] infos = threadMxBean.getThreadInfo(deadlockedThreadIds, true, true);

                    // Add deadlock cycle analysis
                    String deadlockCycle = analyzeDeadlockCycle(infos);
                    if (deadlockCycle != null) {
                        logMessage.append(deadlockCycle).append("\n");
                    }

                    // Add detailed thread information
                    for (ThreadInfo ti : infos)
                        logMessage.append(buildThreadInfoString(ti)).append("\n");
                    log.error(logMessage.toString());


                    handleUiDeadlock(info);
                }
            }
        }
    }

    protected String buildThreadInfoString(ThreadInfo ti) {
        StringBuilder sb = new StringBuilder();
        sb.append(String.format("\"%s\" Id=%d", ti.getThreadName(), ti.getThreadId()));

        // Add lock information if thread is blocked
        if (ti.getLockInfo() != null) {
            sb.append(String.format(" BLOCKED on %s", formatLockInfo(ti.getLockInfo())));
            if (ti.getLockOwnerName() != null) {
                sb.append(String.format(" (owned by \"%s\" Id=%d)", ti.getLockOwnerName(), ti.getLockOwnerId()));
            }
        }
        sb.append("\n");

        // Show owned synchronizers (ReentrantLock, Semaphore, etc.)
        var lockedSynchronizers = ti.getLockedSynchronizers();
        if (lockedSynchronizers.length > 0) {
            sb.append("  Locked synchronizers:\n");
            for (var sync : lockedSynchronizers) {
                sb.append("    - ").append(formatLockInfo(sync)).append("\n");
            }
        }

        // Show owned monitors (synchronized blocks/methods)
        var lockedMonitors = ti.getLockedMonitors();
        if (lockedMonitors.length > 0) {
            sb.append("  Locked monitors:\n");
            for (var monitor : lockedMonitors) {
                sb.append("    - ").append(formatMonitorInfo(monitor)).append("\n");
            }
        }

        // Add stack trace
        sb.append("  Stack trace:\n");
        for (StackTraceElement ste : ti.getStackTrace())
            sb.append("    at " + ste + "\n");
        return sb.toString();
    }


    private void handleUiDeadlock(ThreadInfo uiThreadInfo) {
        if (isInterruptibleThread(uiThreadInfo)) {
            log.info("Calling interrupt() on UI thread to resolve lasting blocking (it is blocked on a call like ReentrantLock.lockInterruptibly())");
            Thread uiThread = threadFromInfo(uiThreadInfo);
            uiThread.interrupt();
            if (!dialogVisible)
                displayDialog(true);
        }
        else {
            log.info("Cannot resolve potential UI deadlock: UI thread is not interruptible (it does not appear to wait in a call that respects interrupt() such as ReentrantLock.lockInterruptibly())");
        }
    }


    public void handleDeadlock(Deadlock deadlock) {
        boolean success = resolveDeadlock(deadlock);
        if (!dialogVisible)
            displayDialog(success);
    }

    public boolean resolveDeadlock(Deadlock deadlock) {
        Thread threadToInterrupt = null;
        for (var info : deadlock.infos) {
            if (isInterruptibleThread(info)) {
                threadToInterrupt = threadFromInfo(info);
                if (threadToInterrupt != null) {
                    log.info("Found thread to interrupt to resolve deadlock: " + info.getThreadName() + " (Id=" + info.getThreadId() + ")");
                    break;
                }
            }
        }

        if (threadToInterrupt != null) {
            log.info("Interrupting thread to resolve deadlock: " + threadToInterrupt.getName());
            threadToInterrupt.interrupt();
            return true;
        }
        else {
            log.info("No suitable thread found to interrupt to resolve deadlock");
            return false;
        }
    }

    protected Thread threadFromInfo(ThreadInfo info) {
        long targetId = info.getThreadId();
        // getAllStackTraces() returns a Map<Thread,StackTraceElement[]> of every live thread
        Set<Thread> threads = Thread.getAllStackTraces().keySet();
        for (Thread t : threads)
            if (t.threadId() == targetId)
                return t;
        return null;  // no live thread with that ID
    }

    protected boolean isInterruptibleThread(ThreadInfo info) {
        // Examine the stack trace to see if the thread is waiting on an interruptible lock.
        StackTraceElement[] stackTrace = info.getStackTrace();
        for (StackTraceElement element : stackTrace) {
            String className = element.getClassName();
            String methodName = element.getMethodName();

            // Currently we only consider ReentrantLock.lockInterruptibly() and ReentrantLock.tryLock()
            if (className.endsWith(".ReentrantLock") && (methodName.equals("lockInterruptibly") || methodName.equals("tryLock")))
                return true;
        }
        return false;
    }

    /**
     * Analyze deadlock cycle and create a visual representation.
     */
    protected String analyzeDeadlockCycle(ThreadInfo[] infos) {
        if (infos == null || infos.length < 2) {
            return null;
        }

        StringBuilder sb = new StringBuilder();
        sb.append("DEADLOCK CYCLE ANALYSIS:\n");

        // Create a map of thread ID to thread info for quick lookup
        Map<Long, ThreadInfo> threadMap = new HashMap<>();
        for (ThreadInfo info : infos) {
            threadMap.put(info.getThreadId(), info);
        }

        // Build the cycle visualization
        sb.append("Lock dependency chain:\n");
        for (ThreadInfo info : infos) {
            String threadName = String.format("\"%s\" (Id=%d)", info.getThreadName(), info.getThreadId());

            if (info.getLockInfo() != null) {
                String lockName = formatLockInfo(info.getLockInfo());
                sb.append("  ").append(threadName).append(" → waiting for ").append(lockName);

                if (info.getLockOwnerName() != null) {
                    sb.append(" (owned by \"").append(info.getLockOwnerName())
                      .append("\" Id=").append(info.getLockOwnerId()).append(")");
                }
                sb.append("\n");
            }
        }

        // Show what each thread owns that might be blocking others
        sb.append("\nLock ownership:\n");
        for (ThreadInfo info : infos) {
            String threadName = String.format("\"%s\" (Id=%d)", info.getThreadName(), info.getThreadId());

            // Show owned synchronizers
            var lockedSynchronizers = info.getLockedSynchronizers();
            if (lockedSynchronizers.length > 0) {
                sb.append("  ").append(threadName).append(" owns:\n");
                for (var sync : lockedSynchronizers) {
                    sb.append("    - ").append(formatLockInfo(sync));

                    // Check if any other deadlocked thread is waiting for this lock
                    String syncName = formatLockInfo(sync);
                    for (ThreadInfo otherInfo : infos) {
                        if (otherInfo.getThreadId() != info.getThreadId() &&
                            otherInfo.getLockInfo() != null &&
                            formatLockInfo(otherInfo.getLockInfo()).equals(syncName)) {
                            sb.append(" (blocking \"").append(otherInfo.getThreadName()).append("\")");
                            break;
                        }
                    }
                    sb.append("\n");
                }
            }
        }

        return sb.toString();
    }

    /**
     * Format lock information for display.
     */
    protected String formatLockInfo(LockInfo lockInfo) {
        if (lockInfo == null)
            return "null";

        String className = lockInfo.getClassName();
        int identityHashCode = lockInfo.getIdentityHashCode();

        // Simplify class name for readability
        String simpleName = className.substring(className.lastIndexOf('.') + 1);

        return String.format("%s@%x", simpleName, identityHashCode);
    }

    /**
     * Format monitor information for display.
     */
    protected String formatMonitorInfo(MonitorInfo monitorInfo) {
        if (monitorInfo == null)
            return "null";

        StringBuilder sb = new StringBuilder();
        sb.append(formatLockInfo(monitorInfo));

        // Add location information if available
        StackTraceElement lockedAt = monitorInfo.getLockedStackFrame();
        if (lockedAt != null) {
            sb.append(" (locked at ").append(lockedAt.getClassName())
              .append(".").append(lockedAt.getMethodName())
              .append(":").append(lockedAt.getLineNumber()).append(")");
        }

        return sb.toString();
    }

    protected void displayDialog(boolean success) {
        dialogVisible = true;
        Display.getDefault().asyncExec(() -> {
            String title = success ? "Deadlock Resolved" : "Deadlock Detected"; // TODO UI or bg thread deadlock, list the threads!!! note: false UI deadlock!!!
            String message = success
                ? "A deadlock was detected and successfully resolved by interrupting a thread."
                : "A deadlock was detected but could not be automatically resolved.";

            message += "\n\nThis is a bug in the IDE. Please help us fix it by reporting this issue at: https://github.com/omnetpp/omnetpp/issues.";
            message += "\n\nInclude the IDE log file (<workspace>/.metadata/.log) with your report and describe what you were doing when this occurred.";

            MessageDialog.openInformation(null, title, message);
            dialogVisible = false;
        });
    }
}
