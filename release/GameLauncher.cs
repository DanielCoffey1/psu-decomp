using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Windows.Forms;

namespace PsuRelease {
    public static class GameLauncher {
        [System.Runtime.InteropServices.DllImport("user32.dll")] static extern uint GetDpiForSystem();

        // Both the settings window and direct launch use these same checks and arguments.
        public static Process Start(string root, Settings settings) {
            settings.Validate();
            using (var gate = new Mutex(false, @"Local\PSURecompiled.GameLaunch")) {
                bool acquired = false;
                try {
                    try { acquired = gate.WaitOne(0); } catch (AbandonedMutexException) { acquired = true; }
                    if (!acquired) throw new InvalidOperationException("Another PSU launch is already in progress.");
                    foreach (string name in new[] { "psu", "psu-staged" }) {
                        foreach (var running in Process.GetProcessesByName(name)) {
                            using (running) {
                                if (!running.HasExited) throw new InvalidOperationException("Close the running PSU game before launching another copy.");
                            }
                        }
                    }
                    if (!File.Exists(Path.Combine(root, "installation.txt")) ||
                        DiscImage.HashFile(Path.Combine(root, "game", "default.xex")) != DiscImage.SupportedXex)
                        throw new InvalidDataException("Installation is incomplete or the game executable does not match. Reinstall from your ISO into a new folder.");
                    var desktop = Screen.PrimaryScreen.WorkingArea; double dpi = GetDpiForSystem();
                    var arguments = settings.Arguments(root, dpi, desktop.Width - (int)(32 * dpi / 96), desktop.Height - (int)(72 * dpi / 96));
                    var game = new Process { StartInfo = new ProcessStartInfo(Path.Combine(root, "bin", "psu.exe"), Settings.CommandLine(arguments)) {
                        WorkingDirectory = Path.Combine(root, "bin"), UseShellExecute = false
                    } };
                    try {
                        if (!game.Start()) throw new IOException("The game could not be started.");
                        return game;
                    } catch { game.Dispose(); throw; }
                } finally { if (acquired) gate.ReleaseMutex(); }
            }
        }
    }
}
