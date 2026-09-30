/*--------------------------------------------------------------*
  Copyright (C) 2006-2025 OpenSim Ltd.

  This file is distributed WITHOUT ANY WARRANTY. See the file
  'License' for details on this and other legal matters.
*--------------------------------------------------------------*/

package org.omnetpp.common.locking;

import java.util.concurrent.locks.ReentrantLock;

import org.omnetpp.common.Debug;


/**
 * Allows using the "try-with-resources" syntax to reduce the boilerplate code
 * needed to protect a critical section with a lock. It eliminates the need for
 * a "finally" block, and merging the locking and "try" lines into one.
 *
 * Original code:
 *
 * <code>
 * lock.lockInterruptibly();
 * try {
 *     ...
 * } finally {
 *     lock.unlock();
 * }
 * </code>
 *
 * With LockGuard:
 *
 * <code>
 * try (var unused = new LockGuard(lock)) {
 *     ...
 * }
 * </code>
 *
 * @author andras
 */
public class LockGuard implements AutoCloseable {
    private final ReentrantLock lock;

    public LockGuard(ReentrantLock lock) {
        this.lock = lock;
        try {
            //Debug.println("LockGuard: Acquiring lock");
            this.lock.lockInterruptibly();
            //Debug.println("LockGuard: Lock acquired");
        } catch (InterruptedException e) {
            Debug.println("LockGuard: Interrupted");
            throw new RuntimeException("Interrupted", e);
        }
    }

    @Override
    public void close() {
        //Debug.println("LockGuard: Releasing lock");
        lock.unlock(); // Automatically release when try block ends
        //Debug.println("LockGuard: Lock released");
    }
}