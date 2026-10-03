import 'package:flutter/widgets.dart';
import 'package:flutter_hbb/mobile/remote_session_lifecycle.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late int clock;
  late int state;
  late int exits;
  late List<Map<String, dynamic>> replayed;
  late RemoteSessionLifecycle lifecycle;
  final error = {'name': 'msgbox', 'type': 'error', 'text': 'any message'};

  setUp(() {
    clock = 100;
    state = 1;
    exits = 0;
    replayed = [];
    lifecycle = RemoteSessionLifecycle(
      readConnectionState: () => state,
      onExit: () => exits++,
      replayEvent: replayed.add,
      now: () => clock,
    );
    lifecycle.handleEvent({'name': 'peer_info'});
  });

  test('A: ended background session exits once without replaying errors', () {
    lifecycle.lifecycleChanged(AppLifecycleState.paused);
    expect(lifecycle.handleEvent(error), isTrue);
    state = 150;
    expect(lifecycle.handleEvent({'name': 'session_disconnected'}), isTrue);
    expect(exits, 0);
    clock = 200;
    lifecycle.lifecycleChanged(AppLifecycleState.resumed);
    lifecycle.lifecycleChanged(AppLifecycleState.resumed);
    expect(lifecycle.handleEvent({'name': 'toast', 'type': 'error'}), isTrue);
    expect(exits, 1);
    expect(replayed, isEmpty);
  });

  test('resume reads native state before queued disconnect/error events', () {
    lifecycle.lifecycleChanged(AppLifecycleState.paused);
    state = 150;
    clock = 200;
    lifecycle.lifecycleChanged(AppLifecycleState.resumed);
    expect(lifecycle.handleEvent(error), isTrue);
    expect(exits, 1);
  });

  test('B/D: three live background cycles retain the session', () {
    for (var i = 0; i < 3; i++) {
      lifecycle.lifecycleChanged(AppLifecycleState.hidden);
      lifecycle.lifecycleChanged(AppLifecycleState.paused);
      clock += 100;
      lifecycle.lifecycleChanged(AppLifecycleState.resumed);
    }
    expect(exits, 0);
    expect(lifecycle.handleEvent(error), isFalse);
  });

  test('C: disconnect after foreground resume keeps the original error', () {
    lifecycle.lifecycleChanged(AppLifecycleState.paused);
    clock = 200;
    lifecycle.lifecycleChanged(AppLifecycleState.resumed);
    state = 250;
    expect(lifecycle.handleEvent(error), isFalse);
    lifecycle.handleEvent({'name': 'session_disconnected'});
    expect(exits, 0);
  });

  test('inactive system dialogs do not count as entering background', () {
    lifecycle.lifecycleChanged(AppLifecycleState.inactive);
    state = 150;
    clock = 200;
    lifecycle.lifecycleChanged(AppLifecycleState.resumed);
    expect(lifecycle.handleEvent(error), isFalse);
    expect(exits, 0);
  });

  test('errors before a successful session retain their handling', () {
    final connecting = RemoteSessionLifecycle(
      readConnectionState: () => 150,
      onExit: () => exits++,
      replayEvent: replayed.add,
      now: () => clock,
    );
    connecting.lifecycleChanged(AppLifecycleState.paused);
    clock = 200;
    connecting.lifecycleChanged(AppLifecycleState.resumed);
    expect(connecting.handleEvent(error), isFalse);
    expect(exits, 0);
  });

  test('nonterminal background messages are replayed for a live session', () {
    lifecycle.lifecycleChanged(AppLifecycleState.paused);
    expect(lifecycle.handleEvent(error), isTrue);
    clock = 200;
    lifecycle.lifecycleChanged(AppLifecycleState.resumed);
    expect(replayed, [error]);
    expect(exits, 0);
  });

  test('an old disconnect event cannot close a reconnected live session', () {
    lifecycle.lifecycleChanged(AppLifecycleState.paused);
    clock = 200;
    lifecycle.lifecycleChanged(AppLifecycleState.resumed);
    lifecycle.handleEvent({'name': 'session_disconnected', 'ended_at': '150'});
    expect(exits, 0);
  });

  test('a native session removed during background is also stale', () {
    lifecycle.lifecycleChanged(AppLifecycleState.paused);
    state = -1;
    clock = 200;
    lifecycle.lifecycleChanged(AppLifecycleState.resumed);
    expect(exits, 1);
    expect(replayed, isEmpty);
  });

  test('a foreground error preceding background is not suppressed', () {
    state = 50;
    lifecycle.lifecycleChanged(AppLifecycleState.paused);
    clock = 200;
    lifecycle.lifecycleChanged(AppLifecycleState.resumed);
    expect(lifecycle.handleEvent(error), isFalse);
    expect(exits, 0);
  });
}
