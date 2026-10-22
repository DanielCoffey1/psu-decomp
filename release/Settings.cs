using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Xml.Serialization;

namespace PsuRelease {
    public sealed class Settings {
        public int Width = 1920, Height = 1080, Scale = 2, Fps = 60;
        public bool Fullscreen = true, Keyboard = true, UnlockExtraMode = true;
        public bool SkipLauncher = false;
        public static readonly int[] Widths = {1280, 1920, 2560, 3840};
        public static readonly int[] Heights = {720, 1080, 1440, 2160};
        // PSU advances simulation per frame. Higher render rates currently speed
        // up gameplay; do not expose the diagnostic uncapping path to players.
        public static readonly int[] FrameRates = {60};
        public void Validate() {
            int i = Array.IndexOf(Widths, Width);
            if (i < 0 || Heights[i] != Height || Scale < 1 || Scale > 3 || !FrameRates.Contains(Fps))
                throw new InvalidDataException("Unsupported graphics settings. Restore the defaults in the launcher.");
        }
        public static Settings Load(string path) {
            if (!File.Exists(path)) return new Settings();
            using (var file = File.OpenRead(path)) {
                var value = (Settings)new XmlSerializer(typeof(Settings)).Deserialize(file); value.Validate(); return value;
            }
        }
        public void Save(string path) {
            Validate(); Directory.CreateDirectory(Path.GetDirectoryName(path));
            string temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try {
                using (var file = File.Create(temp)) new XmlSerializer(typeof(Settings)).Serialize(file, this);
                if (File.Exists(path)) File.Replace(temp, path, null); else File.Move(temp, path);
            } finally { if (File.Exists(temp)) File.Delete(temp); }
        }
        public List<string> Arguments(string root, double dpi = 96, int availableWidth = 0, int availableHeight = 0) {
            Validate();
            // ReXGlue takes logical window dimensions and multiplies by display DPI.
            // The launcher presents physical pixels. Fit windowed mode on the desktop.
            double fit = 1.0;
            if (!Fullscreen && availableWidth > 0 && availableHeight > 0)
                fit = Math.Min(1.0, Math.Min((double)availableWidth / Width, (double)availableHeight / Height));
            dpi = Math.Max(96, dpi);
            int windowWidth = Math.Max(1, (int)Math.Round(Width * fit * 96 / dpi));
            int windowHeight = Math.Max(1, (int)Math.Round(Height * fit * 96 / dpi));
            var args = new List<string> {
                "--game_data_root=" + Path.Combine(root, "game"), "--gpu_plugin=psu",
                "--cache_root=" + Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PSU Recompiled", "cache"),
                // Preserve the game's original video mode. Scale the GPU draws and host window independently.
                "--resolution=720p", "--window_width=" + windowWidth, "--window_height=" + windowHeight,
                "--draw_resolution_scale_x=" + Scale, "--draw_resolution_scale_y=" + Scale,
                "--render_target_path_d3d12=rov", "--fullscreen=" + Fullscreen.ToString().ToLowerInvariant(),
                "--fullscreen_exclusive=false", "--video_mode_refresh_rate=60",
                "--vsync=true", "--psu_max_fps=0", "--psu_movie_present=true",
                "--mnk_mode=" + Keyboard.ToString().ToLowerInvariant(),
                "--psu_unlock_extra_mode=" + UnlockExtraMode.ToString().ToLowerInvariant()
            };
            if (Keyboard) args.AddRange(new[] { "--keybind_start=Return", "--keybind_a=Space", "--keybind_b=Backspace", "--keybind_x=X", "--keybind_y=P", "--keybind_left_trigger=Q", "--keybind_right_trigger=E", "--keybind_rstick_press=V", "--keybind_dpad_up=I", "--keybind_dpad_down=K", "--keybind_dpad_left=J", "--keybind_dpad_right=L" });
            return args;
        }
        // Windows CommandLineToArgvW quoting, including paths ending with a backslash.
        public static string Quote(string value) {
            var output = new StringBuilder("\""); int slashes = 0;
            foreach (char c in value) {
                if (c == '\\') { slashes++; continue; }
                if (c == '"') output.Append('\\', slashes * 2 + 1);
                else output.Append('\\', slashes);
                output.Append(c); slashes = 0;
            }
            output.Append('\\', slashes * 2); return output.Append('"').ToString();
        }
        public static string CommandLine(IEnumerable<string> args) { return String.Join(" ", args.Select(Quote)); }
    }
}
