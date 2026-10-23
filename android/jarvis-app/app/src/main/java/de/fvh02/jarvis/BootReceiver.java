package de.fvh02.jarvis;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Starts Jarvis when the projector is switched on (can be turned off in the pairing screen). */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;
        if (!context.getSharedPreferences(MainActivity.PREFS, Context.MODE_PRIVATE).getBoolean("autostart", true)) return;
        Intent start = new Intent(context, MainActivity.class);
        start.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            context.startActivity(start);
        } catch (RuntimeException ignored) {
            // newer Android versions may not allow starting from the background
        }
    }
}
