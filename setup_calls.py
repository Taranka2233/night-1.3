#!/usr/bin/env python3
"""Внедряет полноэкранный входящий звонок (как в Telegram) в Capacitor Android-проект.
Запускается в CI после `npx cap add android`. Идемпотентен.
Создаёт:
  - CallMessagingService.java  (ловит FCM data-пуш, показывает звонок даже когда приложение убито)
  - IncomingCallActivity.java  (экран звонка поверх блокировки: принять/отклонить)
Патчит AndroidManifest.xml (сервис, activity, разрешения).
"""
import os, re, glob, sys

APP = 'android/app/src/main'

# 1) найти package и путь к java-пакету по MainActivity
pkg_path = None
for p in glob.glob('android/app/src/main/java/**/MainActivity.java', recursive=True):
    pkg_path = os.path.dirname(p); break
if not pkg_path:
    print('MainActivity.java не найден — пропускаю native-звонок'); sys.exit(0)
PKG = pkg_path.split('java/')[1].replace('/', '.')
print('package:', PKG)

# 2) CallMessagingService.java
service_java = '''package %(pkg)s;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import androidx.core.app.NotificationCompat;
import com.google.firebase.messaging.RemoteMessage;
import java.util.Map;

public class CallMessagingService extends com.google.firebase.messaging.FirebaseMessagingService {
    @Override
    public void onMessageReceived(RemoteMessage remoteMessage) {
        Map<String, String> data = remoteMessage.getData();
        if (data != null && "call".equals(data.get("type"))) {
            showIncomingCall(data);
        }
    }

    private void showIncomingCall(Map<String, String> data) {
        String fromName = data.get("fromName"); if (fromName == null) fromName = "Абонент";
        String callType = data.get("callType"); if (callType == null) callType = "audio";
        String fromUid = data.get("fromUid"); if (fromUid == null) fromUid = "";

        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel("calls", "Звонки", NotificationManager.IMPORTANCE_HIGH);
            ch.setDescription("Входящие звонки");
            ch.enableVibration(true);
            ch.setVibrationPattern(new long[]{0, 500, 400, 500, 400, 500});
            ch.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
            nm.createNotificationChannel(ch);
        }

        Intent full = new Intent(this, IncomingCallActivity.class);
        full.putExtra("fromName", fromName);
        full.putExtra("callType", callType);
        full.putExtra("fromUid", fromUid);
        full.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        int piFlags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= 23) piFlags |= PendingIntent.FLAG_IMMUTABLE;
        PendingIntent fullPi = PendingIntent.getActivity(this, 100, full, piFlags);

        String text = "Входящий " + ("video".equals(callType) ? "видеозвонок" : "звонок");
        NotificationCompat.Builder b = new NotificationCompat.Builder(this, "calls")
                .setSmallIcon(android.R.drawable.sym_call_incoming)
                .setContentTitle(fromName)
                .setContentText(text)
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_CALL)
                .setOngoing(true)
                .setAutoCancel(true)
                .setFullScreenIntent(fullPi, true);

        nm.notify(42, b.build());
    }
}
''' % {'pkg': PKG}

# 3) IncomingCallActivity.java — экран поверх блокировки
activity_java = '''package %(pkg)s;

import android.app.Activity;
import android.app.KeyguardManager;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public class IncomingCallActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (Build.VERSION.SDK_INT >= 27) {
            setShowWhenLocked(true);
            setTurnScreenOn(true);
            KeyguardManager km = (KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
            if (km != null) km.requestDismissKeyguard(this, null);
        } else {
            getWindow().addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED |
                WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON |
                WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON |
                WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD);
        }

        String fromName = getIntent().getStringExtra("fromName"); if (fromName == null) fromName = "Абонент";
        String callType = getIntent().getStringExtra("callType"); if (callType == null) callType = "audio";
        final String fromUid = getIntent().getStringExtra("fromUid");

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#0a0a0f"));
        root.setGravity(Gravity.CENTER);
        root.setPadding(48, 96, 48, 96);

        TextView title = new TextView(this);
        title.setText("Входящий " + ("video".equals(callType) ? "видеозвонок" : "звонок"));
        title.setTextColor(Color.parseColor("#00f0ff"));
        title.setTextSize(16);
        title.setGravity(Gravity.CENTER);
        root.addView(title);

        TextView name = new TextView(this);
        name.setText(fromName);
        name.setTextColor(Color.WHITE);
        name.setTextSize(34);
        name.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams nlp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        nlp.setMargins(0, 40, 0, 140);
        name.setLayoutParams(nlp);
        root.addView(name);

        LinearLayout btns = new LinearLayout(this);
        btns.setOrientation(LinearLayout.HORIZONTAL);
        btns.setGravity(Gravity.CENTER);

        Button decline = new Button(this);
        decline.setText("Отклонить");
        decline.setTextColor(Color.WHITE);
        decline.setBackgroundColor(Color.parseColor("#ff003c"));

        Button accept = new Button(this);
        accept.setText("Принять");
        accept.setTextColor(Color.BLACK);
        accept.setBackgroundColor(Color.parseColor("#3aff8f"));

        LinearLayout.LayoutParams blp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        blp.setMargins(24, 0, 24, 0);

        decline.setOnClickListener(v -> { cancelNotif(); finish(); });
        accept.setOnClickListener(v -> {
            cancelNotif();
            Intent i = getPackageManager().getLaunchIntentForPackage(getPackageName());
            if (i != null) {
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
                i.setData(Uri.parse("nightcity://accept?from=" + (fromUid == null ? "" : fromUid)));
                startActivity(i);
            }
            finish();
        });

        btns.addView(decline, blp);
        btns.addView(accept, blp);
        root.addView(btns);

        setContentView(root);
    }

    private void cancelNotif() {
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null) nm.cancel(42);
    }
}
''' % {'pkg': PKG}

open(os.path.join(pkg_path, 'CallMessagingService.java'), 'w', encoding='utf-8').write(service_java)
open(os.path.join(pkg_path, 'IncomingCallActivity.java'), 'w', encoding='utf-8').write(activity_java)
print('Java-файлы созданы')

# 4) патч AndroidManifest.xml
man_path = os.path.join(APP, 'AndroidManifest.xml')
man = open(man_path, encoding='utf-8').read()

# разрешения
perms = [
    'android.permission.USE_FULL_SCREEN_INTENT',
    'android.permission.WAKE_LOCK',
    'android.permission.VIBRATE',
]
add_perms = ''
for p in perms:
    if p not in man:
        add_perms += '    <uses-permission android:name="%s" />\n' % p
if add_perms:
    man = man.replace('<application', add_perms + '    <application', 1)

# сервис + activity внутри <application>
inject = ''
if 'CallMessagingService' not in man:
    inject += '''        <service
            android:name=".CallMessagingService"
            android:exported="false">
            <intent-filter>
                <action android:name="com.google.firebase.MESSAGING_EVENT" />
            </intent-filter>
        </service>
'''
if 'IncomingCallActivity' not in man:
    inject += '''        <activity
            android:name=".IncomingCallActivity"
            android:exported="true"
            android:showWhenLocked="true"
            android:turnScreenOn="true"
            android:excludeFromRecents="true"
            android:launchMode="singleInstance"
            android:theme="@android:style/Theme.Material.NoActionBar" />
'''
if inject:
    # вставить перед закрытием </application>
    man = man.replace('</application>', inject + '    </application>', 1)

open(man_path, 'w', encoding='utf-8').write(man)
print('AndroidManifest.xml пропатчен')

# 5) firebase-messaging на compile classpath приложения
app_gradle = 'android/app/build.gradle'
if os.path.exists(app_gradle):
    g = open(app_gradle, encoding='utf-8').read()
    if 'firebase-messaging' not in g:
        g = re.sub(r'(dependencies\s*\{)',
                   r"\1\n    implementation platform('com.google.firebase:firebase-bom:33.1.2')\n    implementation 'com.google.firebase:firebase-messaging'",
                   g, count=1)
        open(app_gradle, 'w', encoding='utf-8').write(g)
        print('firebase-messaging (BoM) добавлен в app/build.gradle')
    else:
        print('firebase-messaging уже есть в app/build.gradle')
else:
    print('app/build.gradle не найден!')
print('native-звонок внедрён успешно')
