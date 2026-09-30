package org.omnetpp.common.locking;

import java.util.concurrent.locks.ReentrantLock;

import org.eclipse.core.resources.IWorkspace;
import org.eclipse.core.resources.IWorkspaceRoot;
import org.eclipse.core.resources.ResourcesPlugin;
import org.eclipse.core.runtime.CoreException;
import org.eclipse.core.runtime.IProgressMonitor;
import org.eclipse.core.runtime.IStatus;
import org.eclipse.core.runtime.Status;
import org.eclipse.core.runtime.jobs.Job;
import org.eclipse.swt.widgets.Display;
import org.omnetpp.common.Debug;


public class DeadlockExamples {
    private static final ReentrantLock nedResourcesLock = new ReentrantLock();

    public static void workspaceAndNedResourcesDeadlock() throws CoreException, InterruptedException {
        final IWorkspace ws = ResourcesPlugin.getWorkspace();
        final IWorkspaceRoot workspaceRoot = ws.getRoot();
        // still obtain the NedResources instance if needed elsewhere
        //final Object nedResources = NedResourcesPlugin.getNedResources();

        Job job1 = new Job("DeadlockJob1") {
            @Override
            protected IStatus run(IProgressMonitor monitor) {
                try {
                    Debug.println("Job1 Thread " + Thread.currentThread().getName());
                    Debug.println("Job1 locking workspace");
                    synchronized (workspaceRoot) {
                        Debug.println("Job1 locked workspace");
                        Thread.sleep(1000);
                        Debug.println("Job1 locking NED resources");
                        try (var unused = new LockGuard(nedResourcesLock)) {
                            Debug.println("Job1 locked NED resources");
                            Debug.println("Job1 Hello");
                        }
                        Debug.println("Job1 unlocked NED resources");
                        Debug.println("Job1 unlocking workspace");
                    } //synchronized
                    Debug.println("Job1 unlocked workspace");
                } 
                catch (Exception e) {
                    throw new RuntimeException(e);
                }
                return Status.OK_STATUS;
            }
        };

        Job job2 = new Job("DeadlockJob2") {
            @Override
            protected IStatus run(IProgressMonitor monitor) {
                try {
                    Debug.println("Job2 Thread " + Thread.currentThread().getName());
                    Debug.println("Job2 locking NED resources");
                    try (var unused = new LockGuard(nedResourcesLock)) {
                        Debug.println("Job2 locked NED resources");
                        Thread.sleep(1000);
                        Debug.println("Job2 locking workspace");
                        synchronized (workspaceRoot) {
                            Debug.println("Job2 locked workspace");
                            Debug.println("Job2 Hello");
                            Debug.println("Job2 unlocking workspace");
                        } //synchronized
                        Debug.println("Job2 unlocked workspace");
                        Debug.println("Job2 unlocking NED resources");
                    }
                    Debug.println("Job2 unlocked NED resources");
                } 
                catch (Exception e) {
                    throw new RuntimeException(e);
                }
                return Status.OK_STATUS;
            }
        };

        // Schedule both jobs nearly simultaneously
        job1.schedule();
        job2.schedule();

        // Keep JVM alive long enough to observe behavior
        Thread.sleep(10000);
    }

    public static void syncExecUiDeadlock() {
        // Example UI deadlock
        final ReentrantLock lock = new ReentrantLock();
        Job job = new Job("UIDeadlock") {
            @Override
            protected IStatus run(IProgressMonitor monitor) {
                try {
                    Thread.sleep(10000); // Wait for 10 seconds
                } catch (InterruptedException e) {
                    return Status.CANCEL_STATUS;
                }

                System.out.println("Before syncExec!");
                try (var unused = new LockGuard(lock)) {
                    Display.getDefault().syncExec(() -> {
                        System.out.println("Causing deadlock!");
                        try (var unused2 = new LockGuard(lock)) {
                            System.out.println("Never gets here");
                        }
                    });
                }

                return Status.OK_STATUS;
            }
        };
        job.schedule();
    }
}
