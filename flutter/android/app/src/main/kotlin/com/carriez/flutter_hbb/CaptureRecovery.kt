package com.carriez.flutter_hbb

/**
 * Capture recovery decision logic.
 *
 * Separated from [MainService] for JVM-testability. The decision is a pure
 * function of the current capture state; side effects (startCapture,
 * requestMediaProjection) live in [MainService] and are driven by these
 * decisions. Callers log under `XN_CAPTURE_RECOVERY` so the recovery story
 * is observable without coupling this file to Android logging.
 */
object CaptureRecovery {

    enum class Decision {
        NONE,
        REBUILD,
        REQUEST_PERMISSION,
    }

    data class State(
        val captureWanted: Boolean,
        val recoveryRequestInFlight: Boolean,
        val isStart: Boolean,
        val projectionAlive: Boolean,
        val hasRebuiltThisCycle: Boolean,
        val hasRequestedPermissionThisCycle: Boolean,
    )

    /**
     * Decide what to do when `ensureCaptureAvailable` is called.
     *
     * Rules (in order):
     * - captureWanted=false → NONE (user no longer wants capture)
     * - recoveryRequestInFlight → NONE (dedup permission dialogs)
     * - already healthy → NONE (do not disturb a working capture)
     * - both rebuild and permission already attempted in this cycle →
     *   NONE (cycle exhausted; a future authorized connection resets it)
     * - no projection → REQUEST_PERMISSION (unless one was already issued)
     * - stale isStart with projection alive → REBUILD (unless one was
     *   already attempted)
     */
    fun decideEnsure(state: State): Decision {
        if (!state.captureWanted) return Decision.NONE
        if (state.recoveryRequestInFlight) return Decision.NONE
        if (state.isStart && state.projectionAlive) return Decision.NONE
        if (state.hasRebuiltThisCycle && state.hasRequestedPermissionThisCycle) {
            return Decision.NONE
        }
        if (!state.projectionAlive) {
            return if (state.hasRequestedPermissionThisCycle) Decision.NONE
            else Decision.REQUEST_PERMISSION
        }
        return if (state.hasRebuiltThisCycle) Decision.NONE else Decision.REBUILD
    }

    /**
     * Decision for the first-frame timeout of the current generation.
     *
     * - If user no longer wants capture, do nothing.
     * - If first frame was already received, do nothing.
     * - If a permission dialog is open, do nothing.
     * - If projection is missing, nothing to release — stop.
     * - If we already requested permission this cycle, mark the cycle
     *   exhausted (no further escalation).
     * - Otherwise: release the bad projection and request a new permission.
     */
    data class TimeoutDecision(
        val shouldMarkRecoveryFailed: Boolean,
        val shouldReleaseProjection: Boolean,
        val shouldRequestPermission: Boolean,
    )

    fun decideFirstFrameTimeout(
        captureWanted: Boolean,
        firstFrameReceived: Boolean,
        recoveryRequestInFlight: Boolean,
        projectionAlive: Boolean,
        hasRequestedPermissionThisCycle: Boolean,
    ): TimeoutDecision {
        if (!captureWanted || firstFrameReceived || recoveryRequestInFlight) {
            return TimeoutDecision(false, false, false)
        }
        if (!projectionAlive) {
            return TimeoutDecision(false, false, false)
        }
        if (hasRequestedPermissionThisCycle) {
            return TimeoutDecision(true, false, false)
        }
        return TimeoutDecision(false, true, true)
    }

    /**
     * A capture is healthy when it is started, has a live projection, and
     * has produced a first frame. Returning true signals that the cycle
     * budget should be reset for the next session.
     */
    fun shouldResetCycleAfterSuccess(
        isStart: Boolean,
        projectionAlive: Boolean,
        firstFrameReceived: Boolean,
    ): Boolean {
        return isStart && projectionAlive && firstFrameReceived
    }

    /**
     * Decide whether a fresh authorized connection should reset the cycle
     * budget. A new authorized connection is an explicit "user wants
     * capture now" signal, so the bounded-retry budget resets and a new
     * cycle may begin.
     */
    fun shouldResetCycleOnNewConnection(captureWanted: Boolean, isFileTransfer: Boolean): Boolean {
        // File-transfer connections never set captureWanted, so they cannot
        // trigger a reset either.
        return !isFileTransfer
    }
}