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

    class PermissionRequest {
        var generation = 0
            private set
        var inFlight = false
            private set

        fun begin(): Int? {
            if (inFlight) return null
            inFlight = true
            return ++generation
        }

        fun matches(token: Int): Boolean = inFlight && token == generation

        fun finish(token: Int): Boolean {
            if (!matches(token)) return false
            inFlight = false
            return true
        }

        fun invalidate() {
            ++generation
            inFlight = false
        }
    }

    fun canAcceptFirstFrame(generation: Int, currentGeneration: Int, deliveryEnabled: Boolean): Boolean {
        return generation == currentGeneration && deliveryEnabled
    }

    fun canAcceptPermissionResult(request: PermissionRequest, generation: Int, captureWanted: Boolean): Boolean {
        return captureWanted && request.matches(generation)
    }

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
        val resourcesHealthy: Boolean,
        val hasRebuiltThisCycle: Boolean,
        val hasRequestedPermissionThisCycle: Boolean,
    )

    /**
     * Decide what to do when `ensureCaptureAvailable` is called.
     *
     * Rules (in order):
     * - captureWanted=false → NONE (user no longer wants capture)
     * - recoveryRequestInFlight → NONE (dedup permission dialogs)
     * - capture is genuinely healthy (started, projection alive, video
     *   resources valid) → NONE
     * - both rebuild and permission already attempted in this cycle →
     *   NONE (cycle exhausted; a future authorized connection resets it)
     * - no projection → REQUEST_PERMISSION (unless one was already issued)
     * - projection alive but isStart stale or resources invalid →
     *   REBUILD (unless one was already attempted this cycle)
     */
    fun decideEnsure(state: State): Decision {
        if (!state.captureWanted) return Decision.NONE
        if (state.recoveryRequestInFlight) return Decision.NONE
        if (state.isStart && state.projectionAlive && state.resourcesHealthy) {
            return Decision.NONE
        }
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
     * Decision for the first-frame timeout of a specific capture generation.
     *
     * - If the timeout's generation is no longer the current generation, do
     *   nothing (the timeout belongs to a stale capture).
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

    data class TimeoutState(
        val captureWanted: Boolean,
        val firstFrameReceived: Boolean,
        val recoveryRequestInFlight: Boolean,
        val projectionAlive: Boolean,
        val resourcesHealthy: Boolean,
        val hasRequestedPermissionThisCycle: Boolean,
        val timeoutGenerationMatches: Boolean,
    )

    fun decideFirstFrameTimeout(state: TimeoutState): TimeoutDecision {
        if (!state.timeoutGenerationMatches) return TimeoutDecision(false, false, false)
        if (!state.captureWanted || state.firstFrameReceived || state.recoveryRequestInFlight) {
            return TimeoutDecision(false, false, false)
        }
        if (!state.projectionAlive) return TimeoutDecision(false, false, false)
        if (state.hasRequestedPermissionThisCycle) {
            return TimeoutDecision(true, false, false)
        }
        return TimeoutDecision(false, true, true)
    }

    /**
     * Permission-request watchdog decision. A timeout that fires for a stale
     * permission request generation must not clear the in-flight flag of a
     * newer request.
     */
    fun decidePermissionWatchdog(
        watchdogGenerationMatches: Boolean,
        recoveryRequestInFlight: Boolean,
    ): Boolean {
        return watchdogGenerationMatches && recoveryRequestInFlight
    }

    /**
     * A capture is genuinely healthy when it is started, has a live
     * projection, has valid video resources, and has produced a first frame.
     * Returning true signals that the cycle budget should be reset for the
     * next session.
     */
    fun shouldResetCycleAfterSuccess(
        isStart: Boolean,
        projectionAlive: Boolean,
        resourcesHealthy: Boolean,
        firstFrameReceived: Boolean,
    ): Boolean {
        return isStart && projectionAlive && resourcesHealthy && firstFrameReceived
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
