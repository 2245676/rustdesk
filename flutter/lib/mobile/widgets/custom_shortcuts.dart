import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_hbb/models/input_model.dart';
import 'package:flutter_hbb/models/platform_model.dart';

const customShortcutsStorageKey = 'xn-custom-shortcuts-v2';
const customShortcutsLegacyStorageKey = 'xn-custom-shortcuts-v1';
const showChatPrefKey = 'xn-custom-show-chat';
const hideKeyboardTaskBarPrefKey = 'xn-custom-hide-keyboard-task-bar';
const hideKeyboardToolbarPrefKey = 'xn-custom-hide-keyboard-toolbar';
const twoRowsPrefKey = 'xn-custom-shortcuts-two-rows';

enum CustomShortcutType { key, combination, macro, text }

class CustomShortcut {
  const CustomShortcut({
    required this.name,
    required this.value,
    required this.type,
    this.icon = 'keyboard',
    this.visible = true,
  });

  final String name;
  final String value;
  final CustomShortcutType type;
  final String icon;
  final bool visible;

  Map<String, dynamic> toJson() => {
        'name': name,
        'value': value,
        'type': type.name,
        'icon': icon,
        'visible': visible,
      };

  factory CustomShortcut.fromJson(Map<String, dynamic> json) {
    return CustomShortcut(
      name: json['name'] as String? ?? '',
      value: json['value'] as String? ?? '',
      type: CustomShortcutType.values.firstWhere(
        (e) => e.name == json['type'],
        orElse: () => CustomShortcutType.key,
      ),
      icon: json['icon'] as String? ?? 'keyboard',
      visible: json['visible'] as bool? ?? true,
    );
  }

  CustomShortcut copyWith(
          {String? name,
          String? value,
          CustomShortcutType? type,
          String? icon,
          bool? visible}) =>
      CustomShortcut(
        name: name ?? this.name,
        value: value ?? this.value,
        type: type ?? this.type,
        icon: icon ?? this.icon,
        visible: visible ?? this.visible,
      );
}

class CustomShortcutStore {
  static List<CustomShortcut> load() {
    final raw = bind.mainGetLocalOption(key: customShortcutsStorageKey);
    if (raw.isEmpty) {
      return [
        ...defaultCustomShortcuts,
        ...decode(bind.mainGetLocalOption(
            key: customShortcutsLegacyStorageKey)),
      ];
    }
    return decode(raw);
  }

  @visibleForTesting
  static List<CustomShortcut> decode(String raw) {
    if (raw.isEmpty) return [];
    try {
      final data = jsonDecode(raw) as List<dynamic>;
      return data
          .whereType<Map>()
          .map((e) => CustomShortcut.fromJson(Map<String, dynamic>.from(e)))
          .where((e) => e.name.isNotEmpty && e.value.isNotEmpty)
          .toList();
    } catch (_) {
      return [];
    }
  }

  static Future<void> save(List<CustomShortcut> shortcuts) {
    return bind.mainSetLocalOption(
      key: customShortcutsStorageKey,
      value: jsonEncode(shortcuts.map((e) => e.toJson()).toList()),
    );
  }

  static bool get showChat =>
      bind.mainGetLocalOption(key: showChatPrefKey) != 'N';
  static bool get hideKeyboardTaskBar =>
      bind.mainGetLocalOption(key: hideKeyboardTaskBarPrefKey) != 'N';
  static bool get hideKeyboardToolbar =>
      bind.mainGetLocalOption(key: hideKeyboardToolbarPrefKey) == 'Y';
  static bool get twoRows =>
      bind.mainGetLocalOption(key: twoRowsPrefKey) == 'Y';

  static Future<void> setShowChat(bool value) =>
      bind.mainSetLocalOption(
          key: showChatPrefKey, value: value ? 'Y' : 'N');
  static Future<void> setHideKeyboardTaskBar(bool value) =>
      bind.mainSetLocalOption(
          key: hideKeyboardTaskBarPrefKey, value: value ? 'Y' : 'N');
  static Future<void> setHideKeyboardToolbar(bool value) =>
      bind.mainSetLocalOption(
          key: hideKeyboardToolbarPrefKey, value: value ? 'Y' : 'N');
  static Future<void> setTwoRows(bool value) =>
      bind.mainSetLocalOption(key: twoRowsPrefKey, value: value ? 'Y' : 'N');
}

const defaultCustomShortcuts = [
  CustomShortcut(
      name: '左', value: 'VK_LEFT', type: CustomShortcutType.key, icon: 'left'),
  CustomShortcut(
      name: '上', value: 'VK_UP', type: CustomShortcutType.key, icon: 'up'),
  CustomShortcut(
      name: '下',
      value: 'VK_DOWN',
      type: CustomShortcutType.key,
      icon: 'down'),
  CustomShortcut(
      name: '右',
      value: 'VK_RIGHT',
      type: CustomShortcutType.key,
      icon: 'right'),
  CustomShortcut(
      name: '回车',
      value: 'VK_ENTER',
      type: CustomShortcutType.key,
      icon: 'enter'),
];

IconData customShortcutIcon(String icon) {
  switch (icon) {
    case 'copy':
      return Icons.copy;
    case 'left':
      return Icons.keyboard_arrow_left;
    case 'up':
      return Icons.keyboard_arrow_up;
    case 'down':
      return Icons.keyboard_arrow_down;
    case 'right':
      return Icons.keyboard_arrow_right;
    case 'enter':
      return Icons.keyboard_return;
    case 'paste':
      return Icons.content_paste;
    case 'save':
      return Icons.save;
    case 'search':
      return Icons.search;
    case 'terminal':
      return Icons.terminal;
    case 'text':
      return Icons.text_fields;
    case 'bolt':
      return Icons.bolt;
    case 'cut':
      return Icons.content_cut;
    case 'undo':
      return Icons.undo;
    case 'redo':
      return Icons.redo;
    case 'refresh':
      return Icons.refresh;
    case 'home':
      return Icons.home;
    case 'back':
      return Icons.backspace;
    case 'delete':
      return Icons.delete;
    case 'folder':
      return Icons.folder;
    case 'settings':
      return Icons.settings;
    case 'play':
      return Icons.play_arrow;
    case 'pause':
      return Icons.pause;
    case 'star':
      return Icons.star;
    default:
      return Icons.keyboard;
  }
}

void runCustomShortcut(InputModel input, CustomShortcut shortcut) {
  if (shortcut.type == CustomShortcutType.text) {
    bind.sessionInputString(sessionId: input.sessionId, value: shortcut.value);
    return;
  }
  final steps = shortcut.type == CustomShortcutType.macro
      ? splitCustomShortcutMacro(shortcut.value)
      : <String>[shortcut.value];
  for (final step in steps) {
    _sendKeyCombination(input, step.trim());
  }
}

@visibleForTesting
List<String> splitCustomShortcutMacro(String value) =>
    value.split(';').map((s) => s.trim()).toList();

void _sendKeyCombination(InputModel input, String value) {
  if (value.isEmpty) return;
  final parsed = parseShortcutCombination(value);
  if (parsed.key.isEmpty) return;
  final oldCtrl = input.ctrl;
  final oldAlt = input.alt;
  final oldShift = input.shift;
  final oldCommand = input.command;
  input.ctrl = parsed.ctrl;
  input.alt = parsed.alt;
  input.shift = parsed.shift;
  input.command = parsed.command;
  input.inputKey(parsed.key);
  input.ctrl = oldCtrl;
  input.alt = oldAlt;
  input.shift = oldShift;
  input.command = oldCommand;
}

@visibleForTesting
class ParsedShortcutCombination {
  const ParsedShortcutCombination({
    required this.ctrl,
    required this.alt,
    required this.shift,
    required this.command,
    required this.key,
  });

  final bool ctrl;
  final bool alt;
  final bool shift;
  final bool command;
  final String key;
}

@visibleForTesting
ParsedShortcutCombination parseShortcutCombination(String value) {
  final parts = value
      .toUpperCase()
      .split('+')
      .map((e) => e.trim())
      .where((e) => e.isNotEmpty)
      .toList();
  if (parts.isEmpty) {
    return const ParsedShortcutCombination(
        ctrl: false, alt: false, shift: false, command: false, key: '');
  }
  final ctrl = parts.remove('CTRL') || parts.remove('CONTROL');
  final alt = parts.remove('ALT');
  final shift = parts.remove('SHIFT');
  final command =
      parts.remove('CMD') || parts.remove('COMMAND') || parts.remove('META');
  final key = parts.isEmpty ? 'VK_CONTROL' : normalizeShortcutKey(parts.last);
  return ParsedShortcutCombination(
      ctrl: ctrl,
      alt: alt,
      shift: shift,
      command: command,
      key: key);
}

@visibleForTesting
String normalizeShortcutKey(String key) {
  final upper = key.toUpperCase();
  if (upper.startsWith('VK_')) return upper;
  const names = {
    'ENTER',
    'RETURN',
    'ESC',
    'ESCAPE',
    'TAB',
    'SPACE',
    'BACK',
    'DELETE',
    'INSERT',
    'HOME',
    'END',
    'LEFT',
    'RIGHT',
    'UP',
    'DOWN',
    'PRIOR',
    'NEXT'
  };
  if (names.contains(upper)) {
    return upper == 'RETURN' ? 'VK_ENTER' : 'VK_$upper';
  }
  if (RegExp(r'^F(?:[1-9]|1[0-2])$').hasMatch(upper)) {
    return 'VK_$upper';
  }
  if (key.length == 1) return 'VK_$upper';
  return key;
}
