import 'package:flutter/widgets.dart';

class RemoteSessionLifecycle {
  RemoteSessionLifecycle({
    required this.readConnectionState,
    required this.onExit,
    required this.replayEvent,
    int Function()? now,
  }) : now = now ?? (() => DateTime.now().millisecondsSinceEpoch);

  // Native state: -1 absent, 0 connecting, 1 connected, >1 ended at epoch ms.
  final int Function() readConnectionState;
  final VoidCallback onExit;
  final void Function(Map<String, dynamic>) replayEvent;
  final int Function() now;
  final _backgroundIntervals = <List<int>>[];
  final _pendingEvents = <Map<String, dynamic>>[];
  int? _backgroundSince;
  bool _connected = false;
  bool _stale = false;
  bool _exiting = false;

  bool get exiting => _exiting;

  bool _endedInBackground(int state) =>
      state > 1 &&
      ((_backgroundSince != null && state >= _backgroundSince!) ||
          _backgroundIntervals.any((range) =>
              state >= range[0] && state <= range[1]));

  void _checkState() {
    if (_connected && _endedInBackground(readConnectionState())) {
      _stale = true;
      _pendingEvents.clear();
    }
    if (_stale && _backgroundSince == null && !_exiting) {
      _exiting = true;
      onExit();
    }
  }

  void lifecycleChanged(AppLifecycleState state) {
    if (_exiting) return;
    if (state == AppLifecycleState.paused || state == AppLifecycleState.hidden) {
      if (_connected) _backgroundSince ??= now();
    } else if (state == AppLifecycleState.resumed) {
      if (_backgroundSince != null) {
        _backgroundIntervals.add([_backgroundSince!, now()]);
        _backgroundSince = null;
        if (readConnectionState() == -1) _stale = true;
      }
      _checkState();
      if (!_exiting) {
        final pending = List<Map<String, dynamic>>.of(_pendingEvents);
        _pendingEvents.clear();
        for (final event in pending) {
          replayEvent(event);
        }
      }
    }
  }

  bool handleEvent(Map<String, dynamic> event) {
    if (_exiting || _stale) return true;
    if (event['name'] == 'peer_info') _connected = true;
    if (event['name'] == 'session_disconnected') {
      _checkState();
      return true;
    }
    if (event['name'] == 'msgbox' || event['name'] == 'toast') {
      _checkState();
      if (_stale || _exiting) return true;
      if (_connected && _backgroundSince != null) {
        _pendingEvents.add(Map<String, dynamic>.of(event));
        return true;
      }
    }
    return false;
  }
}
