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
        hasRebuiltThisCycle: Boolean = false,
        hasRequestedPermissionThisCycle: Boolean = false,
    ): CaptureRecovery.State {
        return CaptureRecovery.State(
            captureWanted = captureWanted,
            recoveryRequestInFlight = recoveryRequestInFlight,
            isStart = isStart,
            projectionAlive = projectionAlive,
            hasRebuiltThisCycle = hasRebuiltThisCycle,
            hasRequestedPermissionThisCycle = hasRequestedPermissionThisCycle,
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
        // After a rebuild has already been attempted in this cycle, do not
        // rebuild again. The cycle budget is bounded to one rebuild attempt.
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
        // Both A (rebuild) and B (permission request) have already been
        // attempted in this cycle. No further escalation is possible; a
        // future authorized connection must reset the cycle.
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
        // The caller is expected to reset hasRequestedPermissionThisCycle on
        // a fresh authorized connection. After the reset, ensure again
        // returns REQUEST_PERMISSION.
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

    // --- decideFirstFrameTimeout ---

    @Test
    fun `first frame timeout with wanted projection and no prior request escalates`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            captureWanted = true,
            firstFrameReceived = false,
            recoveryRequestInFlight = false,
            projectionAlive = true,
            hasRequestedPermissionThisCycle = false,
        )
        assertEquals(false, decision.shouldMarkRecoveryFailed)
        assertEquals(true, decision.shouldReleaseProjection)
        assertEquals(true, decision.shouldRequestPermission)
    }

    @Test
    fun `first frame received cancels escalation`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            captureWanted = true,
            firstFrameReceived = true,
            recoveryRequestInFlight = false,
            projectionAlive = true,
            hasRequestedPermissionThisCycle = false,
        )
        assertEquals(false, decision.shouldMarkRecoveryFailed)
        assertEquals(false, decision.shouldReleaseProjection)
        assertEquals(false, decision.shouldRequestPermission)
    }

    @Test
    fun `captureWanted false cancels first frame escalation`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            captureWanted = false,
            firstFrameReceived = false,
            recoveryRequestInFlight = false,
            projectionAlive = true,
            hasRequestedPermissionThisCycle = false,
        )
        assertEquals(false, decision.shouldMarkRecoveryFailed)
        assertEquals(false, decision.shouldReleaseProjection)
        assertEquals(false, decision.shouldRequestPermission)
    }

    @Test
    fun `old generation timeout is ignored when captureWanted false`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            captureWanted = false,
            firstFrameReceived = false,
            recoveryRequestInFlight = false,
            projectionAlive = true,
            hasRequestedPermissionThisCycle = false,
        )
        assertEquals(false, decision.shouldRequestPermission)
    }

    @Test
    fun `bounded retry after first-frame timeout marks failed`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            captureWanted = true,
            firstFrameReceived = false,
            recoveryRequestInFlight = false,
            projectionAlive = true,
            hasRequestedPermissionThisCycle = true,
        )
        assertEquals(true, decision.shouldMarkRecoveryFailed)
        assertEquals(false, decision.shouldReleaseProjection)
        assertEquals(false, decision.shouldRequestPermission)
    }

    @Test
    fun `permission in flight cancels first frame escalation`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            captureWanted = true,
            firstFrameReceived = false,
            recoveryRequestInFlight = true,
            projectionAlive = true,
            hasRequestedPermissionThisCycle = false,
        )
        assertEquals(false, decision.shouldMarkRecoveryFailed)
        assertEquals(false, decision.shouldReleaseProjection)
        assertEquals(false, decision.shouldRequestPermission)
    }

    @Test
    fun `missing projection at timeout does nothing`() {
        val decision = CaptureRecovery.decideFirstFrameTimeout(
            captureWanted = true,
            firstFrameReceived = false,
            recoveryRequestInFlight = false,
            projectionAlive = false,
            hasRequestedPermissionThisCycle = false,
        )
        assertEquals(false, decision.shouldMarkRecoveryFailed)
        assertEquals(false, decision.shouldReleaseProjection)
        assertEquals(false, decision.shouldRequestPermission)
    }

    // --- shouldResetCycleAfterSuccess ---

    @Test
    fun `cycle reset on healthy capture`() {
        assertTrue(
            CaptureRecovery.shouldResetCycleAfterSuccess(
                isStart = true,
                projectionAlive = true,
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
                firstFrameReceived = true,
            )
        )
    }
}