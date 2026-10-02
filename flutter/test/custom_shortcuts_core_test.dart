import 'package:flutter_hbb/mobile/widgets/custom_shortcuts.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('CustomShortcut JSON codec', () {
    test('round trips name/value/type/icon/visible', () {
      const s = CustomShortcut(
        name: '复制',
        value: 'CTRL+C',
        type: CustomShortcutType.combination,
        icon: 'copy',
        visible: false,
      );
      final back = CustomShortcut.fromJson(s.toJson());
      expect(back.name, '复制');
      expect(back.value, 'CTRL+C');
      expect(back.type, CustomShortcutType.combination);
      expect(back.icon, 'copy');
      expect(back.visible, false);
    });

    test('missing icon/visible fall back to defaults', () {
      final s = CustomShortcut.fromJson({
        'name': 'A',
        'value': 'VK_A',
        'type': 'key',
      });
      expect(s.icon, 'keyboard');
      expect(s.visible, true);
    });

    test('unknown type falls back to key', () {
      final s = CustomShortcut.fromJson({
        'name': 'A',
        'value': 'VK_A',
        'type': 'unknown',
      });
      expect(s.type, CustomShortcutType.key);
    });

    test('missing name/value are empty strings', () {
      final s = CustomShortcut.fromJson({'type': 'text'});
      expect(s.name, '');
      expect(s.value, '');
      expect(s.type, CustomShortcutType.text);
    });

    test('copyWith overrides only supplied fields', () {
      const s = CustomShortcut(
        name: 'A',
        value: 'VK_A',
        type: CustomShortcutType.key,
      );
      final hidden = s.copyWith(visible: false);
      expect(hidden.name, 'A');
      expect(hidden.value, 'VK_A');
      expect(hidden.type, CustomShortcutType.key);
      expect(hidden.visible, false);
    });
  });

  group('CustomShortcutStore.decode', () {
    test('returns empty list for empty raw', () {
      expect(CustomShortcutStore.decode(''), isEmpty);
    });

    test('returns empty list for malformed JSON', () {
      expect(CustomShortcutStore.decode('{not json'), isEmpty);
      expect(CustomShortcutStore.decode('["nope"]'), isEmpty);
    });

    test('filters items whose name or value is empty', () {
      final raw =
          '[{"name":"","value":"VK_A","type":"key"},{"name":"B","value":"","type":"key"},{"name":"C","value":"VK_C","type":"key"}]';
      expect(CustomShortcutStore.decode(raw), hasLength(1));
      expect(CustomShortcutStore.decode(raw).single.name, 'C');
    });

    test('decodes a well-formed list', () {
      final raw =
          '[{"name":"A","value":"VK_A","type":"key"},{"name":"B","value":"CTRL+C","type":"combination"}]';
      final list = CustomShortcutStore.decode(raw);
      expect(list, hasLength(2));
      expect(list[0].type, CustomShortcutType.key);
      expect(list[1].type, CustomShortcutType.combination);
    });
  });

  group('normalizeShortcutKey', () {
    test('is idempotent for VK_-prefixed names', () {
      expect(normalizeShortcutKey('VK_LEFT'), 'VK_LEFT');
      expect(normalizeShortcutKey('VK_F5'), 'VK_F5');
    });

    test('adds VK_ prefix to canonical key names', () {
      expect(normalizeShortcutKey('ENTER'), 'VK_ENTER');
      expect(normalizeShortcutKey('RETURN'), 'VK_ENTER');
      expect(normalizeShortcutKey('ESC'), 'VK_ESC');
      expect(normalizeShortcutKey('ESCAPE'), 'VK_ESCAPE');
      expect(normalizeShortcutKey('TAB'), 'VK_TAB');
      expect(normalizeShortcutKey('SPACE'), 'VK_SPACE');
      expect(normalizeShortcutKey('HOME'), 'VK_HOME');
      expect(normalizeShortcutKey('PRIOR'), 'VK_PRIOR');
      expect(normalizeShortcutKey('NEXT'), 'VK_NEXT');
    });

    test('adds VK_ prefix to F1..F12', () {
      for (var i = 1; i <= 12; i++) {
        expect(normalizeShortcutKey('F$i'), 'VK_F$i');
      }
    });

    test('wraps single characters with VK_ prefix', () {
      expect(normalizeShortcutKey('a'), 'VK_A');
      expect(normalizeShortcutKey('A'), 'VK_A');
      expect(normalizeShortcutKey('5'), 'VK_5');
    });

    test('normalizes mixed-case input to canonical VK_ form', () {
      expect(normalizeShortcutKey('enter'), 'VK_ENTER');
      expect(normalizeShortcutKey('f5'), 'VK_F5');
      expect(normalizeShortcutKey('vk_left'), 'VK_LEFT');
      expect(normalizeShortcutKey('FooBar'), 'FooBar');
    });

    test('returns unknown names unchanged', () {
      expect(normalizeShortcutKey('UNKNOWN'), 'UNKNOWN');
      expect(normalizeShortcutKey('FooBar'), 'FooBar');
    });
  });

  group('splitCustomShortcutMacro', () {
    test('preserves step order and trims whitespace', () {
      expect(
        splitCustomShortcutMacro('CTRL+C; ALT+TAB; CTRL+V'),
        ['CTRL+C', 'ALT+TAB', 'CTRL+V'],
      );
    });

    test('returns single-element list for non-macro input', () {
      expect(splitCustomShortcutMacro('CTRL+C'), ['CTRL+C']);
    });

    test('keeps empty steps without filtering', () {
      expect(splitCustomShortcutMacro(';CTRL+C;'), ['', 'CTRL+C', '']);
    });

    test('handles empty string', () {
      expect(splitCustomShortcutMacro(''), <String>['']);
    });
  });

  group('parseShortcutCombination', () {
    test('extracts single CTRL modifier', () {
      final p = parseShortcutCombination('CTRL+C');
      expect(p.ctrl, true);
      expect(p.alt, false);
      expect(p.shift, false);
      expect(p.command, false);
      expect(p.key, 'VK_C');
    });

    test('extracts all four modifiers', () {
      final p = parseShortcutCombination('CTRL+ALT+SHIFT+COMMAND+K');
      expect(p.ctrl, true);
      expect(p.alt, true);
      expect(p.shift, true);
      expect(p.command, true);
      expect(p.key, 'VK_K');
    });

    test('accepts CONTROL, CMD, META aliases', () {
      expect(parseShortcutCombination('CONTROL+C').ctrl, true);
      expect(parseShortcutCombination('CMD+C').command, true);
      expect(parseShortcutCombination('COMMAND+C').command, true);
      expect(parseShortcutCombination('META+C').command, true);
    });

    test('returns VK_CONTROL when only modifiers are given', () {
      final p = parseShortcutCombination('CTRL');
      expect(p.ctrl, true);
      expect(p.key, 'VK_CONTROL');
    });

    test('returns empty key for empty or whitespace-only value', () {
      expect(parseShortcutCombination('').key, '');
      expect(parseShortcutCombination('+').key, '');
      expect(parseShortcutCombination('  +  ').key, '');
    });

    test('last token wins when multiple keys appear', () {
      final p = parseShortcutCombination('CTRL+A+B');
      expect(p.ctrl, true);
      expect(p.key, 'VK_B');
    });

    test('uppercases tokens and trims whitespace', () {
      final p = parseShortcutCombination('  ctrl + c  ');
      expect(p.ctrl, true);
      expect(p.key, 'VK_C');
    });
  });

  group('defaultCustomShortcuts', () {
    test('contains exactly the five legacy defaults', () {
      expect(defaultCustomShortcuts, hasLength(5));
    });

    test('matches the legacy Left/Up/Down/Right/Enter mapping', () {
      expect(defaultCustomShortcuts[0].name, '左');
      expect(defaultCustomShortcuts[0].value, 'VK_LEFT');
      expect(defaultCustomShortcuts[0].icon, 'left');
      expect(defaultCustomShortcuts[0].type, CustomShortcutType.key);

      expect(defaultCustomShortcuts[1].name, '上');
      expect(defaultCustomShortcuts[1].value, 'VK_UP');
      expect(defaultCustomShortcuts[1].icon, 'up');

      expect(defaultCustomShortcuts[2].name, '下');
      expect(defaultCustomShortcuts[2].value, 'VK_DOWN');
      expect(defaultCustomShortcuts[2].icon, 'down');

      expect(defaultCustomShortcuts[3].name, '右');
      expect(defaultCustomShortcuts[3].value, 'VK_RIGHT');
      expect(defaultCustomShortcuts[3].icon, 'right');

      expect(defaultCustomShortcuts[4].name, '回车');
      expect(defaultCustomShortcuts[4].value, 'VK_ENTER');
      expect(defaultCustomShortcuts[4].icon, 'enter');
    });

    test('all defaults default to visible', () {
      expect(defaultCustomShortcuts.every((s) => s.visible), isTrue);
    });
  });
}
