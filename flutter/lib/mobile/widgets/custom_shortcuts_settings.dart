import 'package:flutter/material.dart';
import 'package:flutter_hbb/common.dart';

import 'custom_shortcuts.dart';

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
                onReorderItem: (oldIndex, newIndex) => setState(() {
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
                      width: 136,
                      child: Row(children: [
                        ReorderableDragStartListener(
                          index: index,
                          child: const Tooltip(
                            message: '按住拖动排序',
                            child: Icon(Icons.drag_handle),
                          ),
                        ),
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
              initialValue: _type,
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
              initialValue: _icon,
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
