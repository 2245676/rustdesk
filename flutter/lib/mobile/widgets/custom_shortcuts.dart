import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_hbb/common.dart';
import 'package:flutter_hbb/models/input_model.dart';
import 'package:flutter_hbb/models/platform_model.dart';

const _storageKey = 'xn-custom-shortcuts-v2';
const _legacyStorageKey = 'xn-custom-shortcuts-v1';
const _showChatKey = 'xn-custom-show-chat';
const _hideKeyboardTaskBarKey = 'xn-custom-hide-keyboard-task-bar';
const _hideKeyboardToolbarKey = 'xn-custom-hide-keyboard-toolbar';
const _twoRowsKey = 'xn-custom-shortcuts-two-rows';
final customShortcutSettingsOpen = ValueNotifier(false);

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
    final raw = bind.mainGetLocalOption(key: _storageKey);
    if (raw.isEmpty) {
      return [
        ..._defaultShortcuts,
        ..._decode(bind.mainGetLocalOption(key: _legacyStorageKey))
      ];
    }
    return _decode(raw);
  }

  static List<CustomShortcut> _decode(String raw) {
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
      key: _storageKey,
      value: jsonEncode(shortcuts.map((e) => e.toJson()).toList()),
    );
  }

  static bool get showChat => bind.mainGetLocalOption(key: _showChatKey) != 'N';
  // Default to hiding the modifier/task bar while typing, preserving the
  // safer behavior for existing users until they explicitly opt out.
  static bool get hideKeyboardTaskBar =>
      bind.mainGetLocalOption(key: _hideKeyboardTaskBarKey) != 'N';
  static bool get hideKeyboardToolbar =>
      bind.mainGetLocalOption(key: _hideKeyboardToolbarKey) == 'Y';
  static bool get twoRows => bind.mainGetLocalOption(key: _twoRowsKey) == 'Y';

  static Future<void> setShowChat(bool value) =>
      bind.mainSetLocalOption(key: _showChatKey, value: value ? 'Y' : 'N');
  static Future<void> setHideKeyboardTaskBar(bool value) =>
      bind.mainSetLocalOption(
          key: _hideKeyboardTaskBarKey, value: value ? 'Y' : 'N');
  static Future<void> setHideKeyboardToolbar(bool value) =>
      bind.mainSetLocalOption(
          key: _hideKeyboardToolbarKey, value: value ? 'Y' : 'N');
  static Future<void> setTwoRows(bool value) =>
      bind.mainSetLocalOption(key: _twoRowsKey, value: value ? 'Y' : 'N');
}

const _defaultShortcuts = [
  CustomShortcut(
      name: '左', value: 'VK_LEFT', type: CustomShortcutType.key, icon: 'left'),
  CustomShortcut(
      name: '上', value: 'VK_UP', type: CustomShortcutType.key, icon: 'up'),
  CustomShortcut(
      name: '下', value: 'VK_DOWN', type: CustomShortcutType.key, icon: 'down'),
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

/// Executes saved shortcuts using the same remote keyboard channel as the
/// built-in mobile toolbar.
void runCustomShortcut(InputModel input, CustomShortcut shortcut) {
  if (shortcut.type == CustomShortcutType.text) {
    bind.sessionInputString(sessionId: input.sessionId, value: shortcut.value);
    return;
  }
  final steps = shortcut.type == CustomShortcutType.macro
      ? shortcut.value.split(';')
      : [shortcut.value];
  for (final step in steps) {
    _sendKeyCombination(input, step.trim());
  }
}

void _sendKeyCombination(InputModel input, String value) {
  if (value.isEmpty) return;
  final parts = value
      .toUpperCase()
      .split('+')
      .map((e) => e.trim())
      .where((e) => e.isNotEmpty)
      .toList();
  if (parts.isEmpty) return;
  final oldCtrl = input.ctrl;
  final oldAlt = input.alt;
  final oldShift = input.shift;
  final oldCommand = input.command;
  input.ctrl = parts.remove('CTRL') || parts.remove('CONTROL');
  input.alt = parts.remove('ALT');
  input.shift = parts.remove('SHIFT');
  input.command =
      parts.remove('CMD') || parts.remove('COMMAND') || parts.remove('META');
  final key = parts.isEmpty ? 'VK_CONTROL' : _keyName(parts.last);
  input.inputKey(key);
  input.ctrl = oldCtrl;
  input.alt = oldAlt;
  input.shift = oldShift;
  input.command = oldCommand;
}

String _keyName(String key) {
  if (key.startsWith('VK_')) return key;
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
  if (names.contains(key) || RegExp(r'^F(?:[1-9]|1[0-2])$').hasMatch(key)) {
    return key == 'RETURN' ? 'VK_ENTER' : 'VK_$key';
  }
  return key.length == 1 ? 'VK_$key' : key;
}

class CustomShortcutSettingsPage extends StatefulWidget {
  const CustomShortcutSettingsPage({super.key, required this.shortcuts});
  final List<CustomShortcut> shortcuts;

  @override
  State<CustomShortcutSettingsPage> createState() =>
      _CustomShortcutSettingsPageState();
}

class _CustomShortcutSettingsPageState
    extends State<CustomShortcutSettingsPage> {
  late List<CustomShortcut> _shortcuts;

  @override
  void initState() {
    super.initState();
    _shortcuts = List.of(widget.shortcuts);
    customShortcutSettingsOpen.value = true;
    if (isAndroid) gFFI.invokeMethod('enable_soft_keyboard', true);
  }

  @override
  void dispose() {
    if (isAndroid) gFFI.invokeMethod('enable_soft_keyboard', false);
    customShortcutSettingsOpen.value = false;
    super.dispose();
  }

  Future<void> _showToolbarOptions() async {
    var showChat = CustomShortcutStore.showChat;
    var hideKeyboardTaskBar = CustomShortcutStore.hideKeyboardTaskBar;
    var hideKeyboardToolbar = CustomShortcutStore.hideKeyboardToolbar;
    var twoRows = CustomShortcutStore.twoRows;
    await showDialog<void>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('快捷栏选项'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            SwitchListTile(
              title: const Text('显示文字聊天/语音通话'),
              value: showChat,
              onChanged: (value) {
                setDialogState(() => showChat = value);
                CustomShortcutStore.setShowChat(value);
              },
            ),
            SwitchListTile(
              title: const Text('键盘弹出时关闭上任务栏'),
              value: hideKeyboardTaskBar,
              onChanged: (value) {
                setDialogState(() => hideKeyboardTaskBar = value);
                CustomShortcutStore.setHideKeyboardTaskBar(value);
              },
            ),
            SwitchListTile(
              title: const Text('键盘弹出时关闭底部快捷栏'),
              value: hideKeyboardToolbar,
              onChanged: (value) {
                setDialogState(() => hideKeyboardToolbar = value);
                CustomShortcutStore.setHideKeyboardToolbar(value);
              },
            ),
            SwitchListTile(
              title: const Text('双排底部快捷栏'),
              value: twoRows,
              onChanged: (value) {
                setDialogState(() => twoRows = value);
                CustomShortcutStore.setTwoRows(value);
              },
            ),
          ]),
        ),
      ),
    );
  }

  Future<void> _save() async {
    await CustomShortcutStore.save(_shortcuts);
    if (mounted) Navigator.pop(context, _shortcuts);
  }

  Future<void> _edit([CustomShortcut? current, int? index]) async {
    final result = await showDialog<CustomShortcut>(
      context: context,
      builder: (_) => _ShortcutEditor(shortcut: current),
    );
    if (result == null) return;
    setState(() {
      if (index == null) {
        _shortcuts.add(result);
      } else {
        _shortcuts[index] = result;
      }
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('自定义快捷键'),
          actions: [
            IconButton(
                onPressed: _showToolbarOptions,
                icon: const Icon(Icons.tune),
                tooltip: '快捷栏选项'),
            IconButton(
                onPressed: _save, icon: const Icon(Icons.check), tooltip: '保存')
          ],
        ),
        floatingActionButton: FloatingActionButton(
          onPressed: () => _edit(),
          child: const Icon(Icons.add),
        ),
        body: _shortcuts.isEmpty
            ? const Center(child: Text('尚未添加快捷键'))
            : ReorderableListView.builder(
                itemCount: _shortcuts.length,
                onReorder: (oldIndex, newIndex) => setState(() {
                  if (newIndex > oldIndex) newIndex--;
                  final item = _shortcuts.removeAt(oldIndex);
                  _shortcuts.insert(newIndex, item);
                }),
                itemBuilder: (context, index) {
                  final item = _shortcuts[index];
                  return ListTile(
                    key: ValueKey('${item.name}-$index'),
                    leading: Icon(customShortcutIcon(item.icon)),
                    title: Text(item.name),
                    subtitle: Text('${_typeName(item.type)} · ${item.value}'),
                    onTap: () => _edit(item, index),
                    trailing: SizedBox(
                      width: 96,
                      child: Row(children: [
                        IconButton(
                          icon: Icon(item.visible
                              ? Icons.visibility
                              : Icons.visibility_off),
                          tooltip: item.visible ? '隐藏' : '显示',
                          onPressed: () => setState(() => _shortcuts[index] =
                              item.copyWith(visible: !item.visible)),
                        ),
                        IconButton(
                          icon: const Icon(Icons.delete_outline),
                          tooltip: '删除',
                          onPressed: () =>
                              setState(() => _shortcuts.removeAt(index)),
                        ),
                      ]),
                    ),
                  );
                },
              ),
      );
}

String _typeName(CustomShortcutType type) {
  switch (type) {
    case CustomShortcutType.key:
      return '单键';
    case CustomShortcutType.combination:
      return '组合键';
    case CustomShortcutType.macro:
      return '宏组合键';
    case CustomShortcutType.text:
      return '文本输入';
  }
}

class _ShortcutEditor extends StatefulWidget {
  const _ShortcutEditor({this.shortcut});
  final CustomShortcut? shortcut;
  @override
  State<_ShortcutEditor> createState() => _ShortcutEditorState();
}

class _ShortcutEditorState extends State<_ShortcutEditor> {
  late final TextEditingController _name;
  late final TextEditingController _value;
  late CustomShortcutType _type;
  late String _icon;
  late bool _visible;
  static const _icons = [
    'keyboard',
    'left',
    'up',
    'down',
    'right',
    'enter',
    'copy',
    'paste',
    'cut',
    'undo',
    'redo',
    'save',
    'search',
    'terminal',
    'text',
    'bolt',
    'refresh',
    'home',
    'back',
    'delete',
    'folder',
    'settings',
    'play',
    'pause',
    'star',
  ];

  @override
  void initState() {
    super.initState();
    final shortcut = widget.shortcut;
    _name = TextEditingController(text: shortcut?.name ?? '');
    _value = TextEditingController(text: shortcut?.value ?? '');
    _type = shortcut?.type ?? CustomShortcutType.key;
    _icon = shortcut?.icon ?? 'keyboard';
    _visible = shortcut?.visible ?? true;
  }

  @override
  void dispose() {
    _name.dispose();
    _value.dispose();
    super.dispose();
  }

  String get _hint {
    switch (_type) {
      case CustomShortcutType.key:
        return '例如：F5、ENTER、VK_LEFT';
      case CustomShortcutType.combination:
        return '例如：CTRL+C、ALT+F4';
      case CustomShortcutType.macro:
        return '例如：CTRL+C; ALT+TAB; CTRL+V';
      case CustomShortcutType.text:
        return '输入要发送到远端的文本';
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: Text(widget.shortcut == null ? '添加快捷键' : '编辑快捷键'),
        content: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(
                controller: _name,
                decoration: const InputDecoration(labelText: '按钮名称（例如：复制）')),
            DropdownButtonFormField<CustomShortcutType>(
              value: _type,
              decoration: const InputDecoration(labelText: '类型'),
              items: CustomShortcutType.values
                  .map((e) =>
                      DropdownMenuItem(value: e, child: Text(_typeName(e))))
                  .toList(),
              onChanged: (value) => setState(() => _type = value!),
            ),
            TextField(
                controller: _value,
                decoration: InputDecoration(labelText: '内容', hintText: _hint),
                maxLines: _type == CustomShortcutType.text ? 3 : 1),
            DropdownButtonFormField<String>(
              value: _icon,
              decoration: const InputDecoration(labelText: '图标'),
              items: _icons
                  .map((e) => DropdownMenuItem(
                      value: e,
                      child: Row(children: [
                        Icon(customShortcutIcon(e)),
                        const SizedBox(width: 8),
                        Text(e)
                      ])))
                  .toList(),
              onChanged: (value) => setState(() => _icon = value!),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('显示在快捷栏'),
              value: _visible,
              onChanged: (value) => setState(() => _visible = value),
            ),
          ]),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context), child: const Text('取消')),
          FilledButton(
            onPressed: () {
              final name = _name.text.trim();
              final value = _value.text.trim();
              if (name.isEmpty || value.isEmpty) return;
              Navigator.pop(
                  context,
                  CustomShortcut(
                      name: name,
                      value: value,
                      type: _type,
                      icon: _icon,
                      visible: _visible));
            },
            child: const Text('确定'),
          ),
        ],
      );
}
