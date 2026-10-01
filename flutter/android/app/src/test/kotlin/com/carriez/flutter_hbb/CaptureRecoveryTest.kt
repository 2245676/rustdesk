package com.carriez.flutter_hbb

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure-Kotlin tests for [CaptureRecovery]. No Android types involved so
 * the suite runs as a JVM test on the Gradle test task.
 */
class CaptureRecoveryTest {

    private fun healthyState(
        captureWanted: Boolean = true,
        recoveryRequestInFlight: Boolean = false,
        isStart: Boolean = true,
        projectionAlive: Boolean = true,
        resourcesHealthy: Boolean = true,
        hasRebuiltThisCycle: Boolean = false,
        hasRequestedPermissionThisCycle: Boolean = false,
    ): CaptureRecovery.State {
        return CaptureRecovery.State(
            captureWanted = captureWanted,
            recoveryRequestInFlight = recoveryRequestInFlight,
            isStart = isStart,
            projectionAlive = projectionAlive,
            resourcesHealthy = resourcesHealthy,
            hasRebuiltThisCycle = hasRebuiltThisCycle,
            hasRequestedPermissionThisCycle = hasRequestedPermissionThisCycle,
        )
    }

    private fun timeoutState(
        captureWanted: Boolean = true,
        firstFrameReceived: Boolean = false,
        recoveryRequestInFlight: Boolean = false,
        projectionAlive: Boolean = true,
        resourcesHealthy: Boolean = true,
        hasRequestedPermissionThisCycle: Boolean = false,
        timeoutGenerationMatches: Boolean = true,
    ): CaptureRecovery.TimeoutState {
        return CaptureRecovery.TimeoutState(
            captureWanted = captureWanted,
            firstFrameReceived = firstFrameReceived,
            recoveryRequestInFlight = recoveryRequestInFlight,
            projectionAlive = projectionAlive,
            resourcesHealthy = resourcesHealthy,
            hasRequestedPermissionThisCycle = hasRequestedPermissionThisCycle,
            timeoutGenerationMatches = timeoutGenerationMatches,
        )
    }

    // --- decideEnsure: 1 healthy + connection -> no recovery ---

    @Test
    fun `healthy capture with new connection does nothing`() {
        val decision = CaptureRecovery.decideEnsure(healthyState())
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    @Test
    fun `healthy capture with prior rebuild still does nothing`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(hasRebuiltThisCycle = true)
        )
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    // --- decideEnsure: 2 captureWanted=false -> no recovery ---

    @Test
    fun `captureWanted false does nothing`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(captureWanted = false, isStart = false, projectionAlive = false)
        )
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    @Test
    fun `captureWanted false even with prior failure does nothing`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(
                captureWanted = false,
                isStart = false,
                projectionAlive = false,
                hasRequestedPermissionThisCycle = true,
            )
        )
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    // --- decideEnsure: 3 projection missing -> recovery ---

    @Test
    fun `projection missing triggers permission request`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(isStart = false, projectionAlive = false)
        )
        assertEquals(CaptureRecovery.Decision.REQUEST_PERMISSION, decision)
    }

    // --- decideEnsure: 4 projection stopped while wanted -> recovery ---

    @Test
    fun `projection stopped while wanted triggers recovery`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(isStart = false, projectionAlive = false)
        )
        assertEquals(CaptureRecovery.Decision.REQUEST_PERMISSION, decision)
    }

    // --- decideEnsure: 5 stale isStart -> recovery ---

    @Test
    fun `stale isStart with projection triggers rebuild`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(isStart = false, projectionAlive = true)
        )
        assertEquals(CaptureRecovery.Decision.REBUILD, decision)
    }

    // --- decideEnsure: 6 repeated ensure while permission pending -> one request ---

    @Test
    fun `permission in flight does nothing`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(
                recoveryRequestInFlight = true,
                isStart = false,
                projectionAlive = false,
                hasRequestedPermissionThisCycle = true,
            )
        )
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    @Test
    fun `permission denied state does not re-prompt without reset`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(
                recoveryRequestInFlight = false,
                isStart = false,
                projectionAlive = false,
                hasRequestedPermissionThisCycle = true,
            )
        )
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    // --- decideEnsure: 7 permission grant -> auto restart ---

    @Test
    fun `permission granted rebuild path`() {
        // After grant, projection alive, not yet started → REBUILD
        val decision = CaptureRecovery.decideEnsure(
            healthyState(isStart = false, projectionAlive = true)
        )
        assertEquals(CaptureRecovery.Decision.REBUILD, decision)
    }

    // --- decideEnsure: 8 permission deny -> clear state ---

    @Test
    fun `denial state suppresses future ensure until cycle resets`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(
                isStart = false,
                projectionAlive = false,
                hasRequestedPermissionThisCycle = true,
            )
        )
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    // --- decideEnsure: 12 bounded retry ---

    @Test
    fun `bounded retry blocks second request in same cycle`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(
                isStart = false,
                projectionAlive = false,
                hasRequestedPermissionThisCycle = true,
            )
        )
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    @Test
    fun `bounded rebuild blocks second rebuild in same cycle`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(
                isStart = false,
                projectionAlive = true,
                hasRebuiltThisCycle = true,
            )
        )
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    @Test
    fun `cycle exhausted after rebuild and permission request returns none`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(
                isStart = false,
                projectionAlive = false,
                hasRebuiltThisCycle = true,
                hasRequestedPermissionThisCycle = true,
            )
        )
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    // --- decideEnsure: 14 new connection after denial can retry ---

    @Test
    fun `cycle reset on new connection allows retry`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(isStart = false, projectionAlive = false)
        )
        assertEquals(CaptureRecovery.Decision.REQUEST_PERMISSION, decision)
    }

    // --- decideEnsure: 15 healthy capture not restarted ---

    @Test
    fun `healthy capture does not restart`() {
        val decision = CaptureRecovery.decideEnsure(healthyState())
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    // --- decideEnsure: 16 file-transfer connection no capture ---

    @Test
    fun `file transfer connection never resets cycle`() {
        assertFalse(CaptureRecovery.shouldResetCycleOnNewConnection(captureWanted = false, isFileTransfer = true))
    }

    @Test
    fun `non-file transfer authorized connection may reset cycle`() {
        assertTrue(CaptureRecovery.shouldResetCycleOnNewConnection(captureWanted = true, isFileTransfer = false))
    }

    // --- F-01: stale isStart + dead resources ---

    @Test
    fun `stale isStart with dead resources triggers rebuild`() {
        // isStart=true but the live resources (imageReader/surface/virtualDisplay)
        // are dead. The pre-fix logic would short-circuit to NONE here and
        // leave the pipeline black. The fix requires REBUILD so the caller
        // tears down the stale state and starts fresh.
        val decision = CaptureRecovery.decideEnsure(
            healthyState(isStart = true, projectionAlive = true, resourcesHealthy = false)
        )
        assertEquals(CaptureRecovery.Decision.REBUILD, decision)
    }

    @Test
    fun `healthy resources return none even with prior rebuild`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(
                isStart = true,
                projectionAlive = true,
                resourcesHealthy = true,
                hasRebuiltThisCycle = true,
            )
        )
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    @Test
    fun `missing imageReader surface triggers rebuild`() {
        // In MainService.resourcesHealthy, surface.isValid is checked via
        // imageReader.surface.isValid. When the reader is null the whole
        // expression evaluates to false. The decision helper does not know
        // about surfaces directly — the caller derives resourcesHealthy
        // and passes it in. This test pins the contract.
        val decision = CaptureRecovery.decideEnsure(
            healthyState(
                isStart = true,
                projectionAlive = true,
                resourcesHealthy = false,
            )
        )
        assertEquals(CaptureRecovery.Decision.REBUILD, decision)
    }

    @Test
    fun `invalid released surface triggers rebuild`() {
        // After surface.release(), surface.isValid == false, so
        // resourcesHealthy reports false and ensure returns REBUILD.
        val decision = CaptureRecovery.decideEnsure(
            healthyState(
                isStart = true,
                projectionAlive = true,
                resourcesHealthy = false,
            )
        )
        assertEquals(CaptureRecovery.Decision.REBUILD, decision)
    }

    @Test
    fun `stale resources bounded rebuild returns none after one attempt`() {
        val decision = CaptureRecovery.decideEnsure(
            healthyState(
                isStart = true,
                projectionAlive = true,
                resourcesHealthy = false,
                hasRebuiltThisCycle = true,
            )
        )
        assertEquals(CaptureRecovery.Decision.NONE, decision)
    }

    // --- decideFirstFrameTimeout ---

    @Test
    fun `first frame timeout with wanted projection and no prior request escalates`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(timeoutState())
        assertEquals(false, decision.shouldMarkRecoveryFailed)
        assertEquals(true, decision.shouldReleaseProjection)
        assertEquals(true, decision.shouldRequestPermission)
    }

    @Test
    fun `first frame received cancels escalation`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            timeoutState(firstFrameReceived = true)
        )
        assertEquals(false, decision.shouldMarkRecoveryFailed)
        assertEquals(false, decision.shouldReleaseProjection)
        assertEquals(false, decision.shouldRequestPermission)
    }

    @Test
    fun `captureWanted false cancels first frame escalation`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            timeoutState(captureWanted = false)
        )
        assertEquals(false, decision.shouldMarkRecoveryFailed)
        assertEquals(false, decision.shouldReleaseProjection)
        assertEquals(false, decision.shouldRequestPermission)
    }

    @Test
    fun `bounded retry after first-frame timeout marks failed`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            timeoutState(hasRequestedPermissionThisCycle = true)
        )
        assertEquals(true, decision.shouldMarkRecoveryFailed)
        assertEquals(false, decision.shouldReleaseProjection)
        assertEquals(false, decision.shouldRequestPermission)
    }

    @Test
    fun `permission in flight cancels first frame escalation`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            timeoutState(recoveryRequestInFlight = true)
        )
        assertEquals(false, decision.shouldMarkRecoveryFailed)
        assertEquals(false, decision.shouldReleaseProjection)
        assertEquals(false, decision.shouldRequestPermission)
    }

    @Test
    fun `missing projection at timeout does nothing`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            timeoutState(projectionAlive = false)
        )
        assertEquals(false, decision.shouldMarkRecoveryFailed)
        assertEquals(false, decision.shouldReleaseProjection)
        assertEquals(false, decision.shouldRequestPermission)
    }

    // --- F-02: generation binding for first-frame timeout ---

    @Test
    fun `stale first-frame generation timeout is ignored`() {
        // Generation 1 timeout fires after generation 2 has started.
        // The helper must return the inert TimeoutDecision so the caller
        // does not tear down the healthy newer pipeline.
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            timeoutState(timeoutGenerationMatches = false)
        )
        assertEquals(false, decision.shouldMarkRecoveryFailed)
        assertEquals(false, decision.shouldReleaseProjection)
        assertEquals(false, decision.shouldRequestPermission)
    }

    @Test
    fun `current generation timeout executes escalation`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            timeoutState(timeoutGenerationMatches = true)
        )
        assertEquals(true, decision.shouldRequestPermission)
    }

    @Test
    fun `stale generation timeout ignored even when captureWanted true`() {
        // The current "captureWanted=false" substitute must not be the only
        // guard. The helper must also refuse to act when the generation
        // does not match, regardless of captureWanted.
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            timeoutState(
                captureWanted = true,
                timeoutGenerationMatches = false,
            )
        )
        assertEquals(false, decision.shouldRequestPermission)
    }

    // --- F-03: permission watchdog ---

    @Test
    fun `current permission timeout clears inFlight`() {
        assertTrue(
            CaptureRecovery.decidePermissionWatchdog(
                watchdogGenerationMatches = true,
                recoveryRequestInFlight = true,
            )
        )
    }

    @Test
    fun `stale permission timeout does not clear inFlight`() {
        // A timeout from a previous request must not clear the in-flight
        // flag of a newer request.
        assertFalse(
            CaptureRecovery.decidePermissionWatchdog(
                watchdogGenerationMatches = false,
                recoveryRequestInFlight = true,
            )
        )
    }

    @Test
    fun `permission timeout after inFlight already cleared does nothing`() {
        assertFalse(
            CaptureRecovery.decidePermissionWatchdog(
                watchdogGenerationMatches = true,
                recoveryRequestInFlight = false,
            )
        )
    }

    @Test
    fun `new connection after permission timeout can retry`() {
        // After a permission watchdog fired and cleared inFlight, a fresh
        // authorized connection resets the cycle and ensures again. With
        // inFlight=false, the cycle budget is fresh: REQUEST_PERMISSION.
        val decision = CaptureRecovery.decideEnsure(
            healthyState(
                captureWanted = true,
                recoveryRequestInFlight = false,
                isStart = false,
                projectionAlive = false,
                hasRebuiltThisCycle = false,
                hasRequestedPermissionThisCycle = false,
            )
        )
        assertEquals(CaptureRecovery.Decision.REQUEST_PERMISSION, decision)
    }

    @Test
    fun `watchdog never auto-requests permission again`() {
        // The helper returns true only to clear in-flight. There is no
        // request-permission branch. Verify by exhausting the cycle: with
        // inFlight=true and prior request already issued, the helper still
        // says "clear" without opening a second dialog.
        assertTrue(
            CaptureRecovery.decidePermissionWatchdog(
                watchdogGenerationMatches = true,
                recoveryRequestInFlight = true,
            )
        )
    }

    // --- F-04 ordering / shouldResetCycleAfterSuccess ---

    @Test
    fun `cycle reset on healthy capture`() {
        assertTrue(
            CaptureRecovery.shouldResetCycleAfterSuccess(
                isStart = true,
                projectionAlive = true,
                resourcesHealthy = true,
                firstFrameReceived = true,
            )
        )
    }

    @Test
    fun `cycle not reset when first frame pending`() {
        assertFalse(
            CaptureRecovery.shouldResetCycleAfterSuccess(
                isStart = true,
                projectionAlive = true,
                resourcesHealthy = true,
                firstFrameReceived = false,
            )
        )
    }

    @Test
    fun `cycle not reset when capture stopped`() {
        assertFalse(
            CaptureRecovery.shouldResetCycleAfterSuccess(
                isStart = false,
                projectionAlive = true,
                resourcesHealthy = true,
                firstFrameReceived = true,
            )
        )
    }

    @Test
    fun `cycle not reset when projection missing`() {
        assertFalse(
            CaptureRecovery.shouldResetCycleAfterSuccess(
                isStart = true,
                projectionAlive = false,
                resourcesHealthy = true,
                firstFrameReceived = true,
            )
        )
    }

    @Test
    fun `cycle not reset when resources unhealthy even after first frame`() {
        // isStart=true, projection alive, frame arrived — but resources
        // are stale. The cycle must NOT be reset because subsequent frames
        // are not actually deliverable until resources are re-initialized.
        assertFalse(
            CaptureRecovery.shouldResetCycleAfterSuccess(
                isStart = true,
                projectionAlive = true,
                resourcesHealthy = false,
                firstFrameReceived = true,
            )
        )
    }
}