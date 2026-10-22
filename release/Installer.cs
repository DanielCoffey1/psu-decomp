using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Threading;

namespace PsuRelease {
    public static class Installer {
        public static string Install(string iso, string destination, Settings settings, bool shortcut, Action<int, string> progress, CancellationToken cancel) {
            destination = Path.GetFullPath(destination).TrimEnd('\\', '/');
            if (String.IsNullOrEmpty(Path.GetFileName(destination)) || File.Exists(destination) || Directory.Exists(destination))
                throw new IOException("Choose a new installation folder. Existing folders are never overwritten.");
            string parent = Path.GetDirectoryName(destination);
            // Stage beside the destination so the final directory rename is atomic.
            string staging = Path.Combine(parent, ".psu-install-" + Guid.NewGuid().ToString("N"));
            bool created = false;
            try {
                progress(0, "Checking your ISO...");
                using (var disc = new DiscImage(iso)) {
                    disc.VerifyGame(); cancel.ThrowIfCancellationRequested();
                    var drive = new DriveInfo(Path.GetPathRoot(destination));
                    if (drive.AvailableFreeSpace < disc.ExtractedSize + 512L * 1024 * 1024) throw new IOException("Not enough free space. Allow at least " + ((disc.ExtractedSize + 512L * 1024 * 1024) / 1073741824.0).ToString("F1") + " GB.");
                    Directory.CreateDirectory(parent); Directory.CreateDirectory(staging); created = true;
                    using (var payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")) {
                        if (payload == null) throw new InvalidDataException("Installer payload is missing.");
                        ExtractPayload(payload, staging, cancel);
                    }
                    progress(3, "Extracting game data...");
                    int lastPercent = -1; var lastUpdate = DateTime.MinValue;
                    disc.Extract(Path.Combine(staging, "game"), (percent, name) => {
                        if (percent != lastPercent || (DateTime.UtcNow - lastUpdate).TotalMilliseconds > 200) {
                            progress(3 + percent * 94 / 100, "Extracting " + name); lastPercent = percent; lastUpdate = DateTime.UtcNow;
                        }
                    }, cancel);
                }
                cancel.ThrowIfCancellationRequested();
                if (DiscImage.HashFile(Path.Combine(staging, "game", "default.xex")) != DiscImage.SupportedXex) throw new InvalidDataException("Extracted executable verification failed.");
                GameIcon.Install(staging);
                settings.Save(Path.Combine(staging, "settings.xml"));
                File.WriteAllText(Path.Combine(staging, "installation.txt"), "PSU Recompiled " + Program.Version + "\r\nXEX SHA-256: " + DiscImage.SupportedXex + "\r\n");
                cancel.ThrowIfCancellationRequested();
                Directory.Move(staging, destination); created = false;
                string warning = "";
                if (shortcut) {
                    try { CreateShortcut(destination); }
                    catch (Exception ex) { warning = "Installed successfully, but the desktop shortcut could not be created: " + ex.Message + "\nOpen PSU Launcher.exe in the installation folder."; }
                }
                progress(100, "Installation complete."); return warning;
            } finally {
                // Only the newly created GUID staging folder is eligible for rollback.
                if (created && Directory.Exists(staging) && Path.GetDirectoryName(Path.GetFullPath(staging)).Equals(parent, StringComparison.OrdinalIgnoreCase)
                    && Path.GetFileName(staging).StartsWith(".psu-install-", StringComparison.Ordinal)) {
                    Directory.Delete(staging, true);
                }
            }
        }
        static void ExtractPayload(Stream stream, string root, CancellationToken cancel) {
            using (var zip = new ZipArchive(stream, ZipArchiveMode.Read)) {
                var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                long total = 0;
                foreach (var entry in zip.Entries) {
                    cancel.ThrowIfCancellationRequested();
                    string relative = entry.FullName.Replace('\\', '/');
                    if (!names.Add(relative) || entry.Length > 128L * 1024 * 1024 || (total += entry.Length) > 512L * 1024 * 1024)
                        throw new InvalidDataException("Invalid installer payload.");
                    string output = DiscImage.SafePath(root, relative);
                    Directory.CreateDirectory(Path.GetDirectoryName(output));
                    using (var input = entry.Open()) using (var file = new FileStream(output, FileMode.CreateNew, FileAccess.Write)) input.CopyTo(file);
                }
            }
            foreach (string line in File.ReadAllLines(Path.Combine(root, "payload.sha256"))) {
                if (line.Length < 67 || line.Substring(64, 2) != "  ") throw new InvalidDataException("Invalid payload checksums.");
                string file = DiscImage.SafePath(root, line.Substring(66));
                if (DiscImage.HashFile(file) != line.Substring(0, 64)) throw new InvalidDataException("Package verification failed: " + Path.GetFileName(file));
            }
            foreach (string required in new[] { "PSU Launcher.exe", "bin/psu.exe", "bin/rexruntime.dll", "bin/rexgpu-psu.dll" })
                if (!File.Exists(DiscImage.SafePath(root, required))) throw new InvalidDataException("Incomplete package: " + required);
        }
        public static void CreateShortcut(string root) {
            string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            string path = Path.Combine(desktop, "Phantasy Star Universe Recompiled.lnk");
            // Do not replace a user's existing shortcut to another installation.
            if (File.Exists(path)) path = Path.Combine(desktop, "Phantasy Star Universe Recompiled " + DateTime.Now.ToString("yyyyMMdd-HHmmss") + ".lnk");
            Type type = Type.GetTypeFromProgID("WScript.Shell"); object shell = Activator.CreateInstance(type);
            object link = null;
            try {
                link = type.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { path });
                Type lt = link.GetType();
                lt.InvokeMember("TargetPath", BindingFlags.SetProperty, null, link, new object[] { Path.Combine(root, "PSU Launcher.exe") });
                lt.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, link, new object[] { root });
                lt.InvokeMember("Description", BindingFlags.SetProperty, null, link, new object[] { "Play PSU Recompiled or change graphics settings" });
                lt.InvokeMember("IconLocation", BindingFlags.SetProperty, null, link, new object[] { Path.Combine(root, GameIcon.FileName) + ",0" });
                lt.InvokeMember("Save", BindingFlags.InvokeMethod, null, link, null);
            } finally {
                if (link != null) System.Runtime.InteropServices.Marshal.FinalReleaseComObject(link);
                System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell);
            }
        }
        public static void RefreshShortcutIcons(string root) {
            string target = Path.GetFullPath(Path.Combine(root, "PSU Launcher.exe"));
            string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            Type type = Type.GetTypeFromProgID("WScript.Shell"); object shell = Activator.CreateInstance(type);
            try {
                foreach (string path in Directory.EnumerateFiles(desktop, "*.lnk")) {
                    object link = null;
                    try {
                        link = type.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { path });
                        Type lt = link.GetType();
                        string existingTarget = (string)lt.InvokeMember("TargetPath", BindingFlags.GetProperty, null, link, null);
                        if (!String.Equals(existingTarget, target, StringComparison.OrdinalIgnoreCase)) continue;
                        lt.InvokeMember("IconLocation", BindingFlags.SetProperty, null, link, new object[] { Path.Combine(root, GameIcon.FileName) + ",0" });
                        lt.InvokeMember("Save", BindingFlags.InvokeMethod, null, link, null);
                    } finally { if (link != null) System.Runtime.InteropServices.Marshal.FinalReleaseComObject(link); }
                }
            } finally { System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell); }
        }
    }
}
