#!/usr/bin/env python3
"""Внедряет динамические иконки (как в Telegram) в сгенерированный Capacitor Android-проект.
Запускается в CI после `npx cap add android`. Идемпотентен."""
import os, re, glob, shutil, sys

APP = 'android/app/src/main'
PKG_PATH = None

# 1) найти package (например net.nightcity.chat) по MainActivity
for p in glob.glob('android/app/src/main/java/**/MainActivity.java', recursive=True):
    PKG_PATH = os.path.dirname(p)
    break
if not PKG_PATH:
    print('MainActivity.java не найден'); sys.exit(1)
PKG = PKG_PATH.split('java/')[1].replace('/', '.')
print('package:', PKG)

# 2) скопировать иконки appicon_XX.png в drawable-nodpi
dst = os.path.join(APP, 'res', 'drawable-nodpi')
os.makedirs(dst, exist_ok=True)
icons = sorted(glob.glob('appicon_*.png')) or sorted(glob.glob('appicons/appicon_*.png'))
if not icons:
    print('иконки appicon_*.png не найдены — пропускаю динамические иконки'); sys.exit(0)
names = []
for f in icons:
    base = os.path.basename(f).lower()
    shutil.copy(f, os.path.join(dst, base))
    names.append(os.path.splitext(base)[0])  # appicon_01
print('иконок скопировано:', len(names))

# 3) патч AndroidManifest.xml
man_path = os.path.join(APP, 'AndroidManifest.xml')
man = open(man_path, encoding='utf-8').read()

if 'activity-alias' not in man:
    # убрать LAUNCHER intent-filter из MainActivity (он переедет в алиасы)
    act = re.search(r'(<activity[^>]*MainActivity.*?</activity>)', man, re.S)
    if not act:
        print('activity MainActivity не найдена'); sys.exit(1)
    act_xml = act.group(1)
    act_new = re.sub(
        r'\s*<intent-filter>\s*<action android:name="android.intent.action.MAIN"\s*/>\s*'
        r'<category android:name="android.intent.category.LAUNCHER"\s*/>\s*</intent-filter>',
        '', act_xml, flags=re.S)
    man = man.replace(act_xml, act_new)

    # иконка приложения по умолчанию -> appicon_10
    man = re.sub(r'(<application[^>]*?android:icon=")[^"]*(")',
                 r'\g<1>@drawable/appicon_10\g<2>', man, count=1)
    man = re.sub(r'(<application[^>]*?android:roundIcon=")[^"]*(")',
                 r'\g<1>@drawable/appicon_10\g<2>', man, count=1)

    # алиасы: Icon01..Icon10, включён только Icon10
    aliases = []
    for n in names:
        num = n.split('_')[1]                # 01..10
        alias = 'Icon' + num
        enabled = 'true' if num == '10' else 'false'
        aliases.append(f'''        <activity-alias
            android:name=".{alias}"
            android:enabled="{enabled}"
            android:exported="true"
            android:icon="@drawable/{n}"
            android:targetActivity=".MainActivity">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity-alias>''')
    man = man.replace('</application>', '\n'.join(aliases) + '\n    </application>')
    open(man_path, 'w', encoding='utf-8').write(man)
    print('AndroidManifest.xml пропатчен: алиасы добавлены')
else:
    print('алиасы уже есть — пропускаю патч манифеста')

# 4) плагин IconChanger
plugin_src = f'''package {PKG};

import android.content.ComponentName;
import android.content.pm.PackageManager;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "IconChanger")
public class IconChangerPlugin extends Plugin {{
    private static final String[] ALL = {{"Icon01","Icon02","Icon03","Icon04","Icon05","Icon06","Icon07","Icon08","Icon09","Icon10"}};

    @PluginMethod
    public void setIcon(PluginCall call) {{
        String icon = call.getString("icon");
        if (icon == null) {{ call.reject("icon required"); return; }}
        PackageManager pm = getContext().getPackageManager();
        String pkg = getContext().getPackageName();
        for (String a : ALL) {{
            int state = a.equals(icon)
                ? PackageManager.COMPONENT_ENABLED_STATE_ENABLED
                : PackageManager.COMPONENT_ENABLED_STATE_DISABLED;
            pm.setComponentEnabledSetting(new ComponentName(pkg, pkg + "." + a), state, PackageManager.DONT_KILL_APP);
        }}
        call.resolve();
    }}
}}
'''
open(os.path.join(PKG_PATH, 'IconChangerPlugin.java'), 'w', encoding='utf-8').write(plugin_src)
print('IconChangerPlugin.java создан')

# 5) регистрация плагина в MainActivity
ma_path = os.path.join(PKG_PATH, 'MainActivity.java')
ma = open(ma_path, encoding='utf-8').read()
if 'IconChangerPlugin' not in ma:
    if 'import android.os.Bundle;' not in ma:
        ma = ma.replace('import com.getcapacitor.BridgeActivity;',
                        'import android.os.Bundle;\nimport com.getcapacitor.BridgeActivity;')
    body = ('    @Override\n'
            '    public void onCreate(Bundle savedInstanceState) {\n'
            '        registerPlugin(IconChangerPlugin.class);\n'
            '        super.onCreate(savedInstanceState);\n'
            '    }\n')
    ma = re.sub(r'(public class MainActivity extends BridgeActivity \{)',
                r'\1\n' + body, ma, count=1)
    open(ma_path, 'w', encoding='utf-8').write(ma)
    print('MainActivity.java: плагин зарегистрирован')
else:
    print('плагин уже зарегистрирован')

print('OK: динамические иконки настроены')
