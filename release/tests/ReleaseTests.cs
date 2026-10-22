using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;

namespace PsuRelease {
    public static class ReleaseTests {
        static int checks;
        static void Assert(bool value, string label) { if (!value) throw new Exception(label); checks++; }
        static void Reject(Action action, string label) { try { action(); } catch (InvalidDataException) { checks++; return; } throw new Exception(label); }
        static string Fixture(string root, string name, bool cycle, bool truncated) {
            var bytes = new byte[75000]; byte[] magic = Encoding.ASCII.GetBytes("MICROSOFT*XBOX*MEDIA");
            Array.Copy(magic, 0, bytes, 65536, magic.Length); Array.Copy(BitConverter.GetBytes(34U), 0, bytes, 65556, 4); Array.Copy(BitConverter.GetBytes(2048U), 0, bytes, 65560, 4);
            int offset = 34 * 2048;
            Array.Copy(BitConverter.GetBytes(truncated ? 1000U : 36U), 0, bytes, offset + 4, 4);
            Array.Copy(BitConverter.GetBytes(4U), 0, bytes, offset + 8, 4); bytes[offset + 13] = (byte)name.Length;
            Array.Copy(Encoding.ASCII.GetBytes(name), 0, bytes, offset + 14, name.Length);
            if (cycle) { // Root points to another entry, which points to itself.
                Array.Copy(BitConverter.GetBytes((ushort)16), 0, bytes, offset, 2);
                Array.Copy(bytes, offset, bytes, offset + 64, 14 + name.Length);
            }
            Array.Copy(Encoding.ASCII.GetBytes("test"), 0, bytes, 36 * 2048, 4);
            string path = Path.Combine(root, Guid.NewGuid().ToString("N") + ".iso"); File.WriteAllBytes(path, bytes); return path;
        }
        public static int Main(string[] args) {
            string root = Path.Combine(Path.GetTempPath(), "psu-release-tests-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(root);
            try {
                foreach (string unsafeName in new[] { "../bad", "C:/bad", "foo/../bad", "CON", "a.", "a ", "a:b", "a//b" })
                    Reject(() => DiscImage.SafePath(root, unsafeName), "Accepted unsafe path: " + unsafeName);
                string valid = Fixture(root, "DATA.BIN", false, false);
                using (var disc = new DiscImage(valid)) {
                    Assert(disc.ExtractedSize == 4, "Wrong extraction size");
                    Reject(() => disc.VerifyGame(), "Accepted unsupported executable");
                    disc.Extract(Path.Combine(root, "extracted"), (p, s) => {}, CancellationToken.None);
                    Assert(File.ReadAllText(Path.Combine(root, "extracted", "DATA.BIN")) == "test", "Corrupt extraction");
                }
                Reject(() => { using (var d = new DiscImage(Fixture(root, "..", false, false))) {} }, "Accepted traversal");
                Reject(() => { using (var d = new DiscImage(Fixture(root, "DATA", true, false))) {} }, "Accepted directory cycle");
                Reject(() => { using (var d = new DiscImage(Fixture(root, "DATA", false, true))) {} }, "Accepted out-of-bounds extent");
                foreach (int frameRate in Settings.FrameRates) {
                    var settings = new Settings { Width = 3840, Height = 2160, Scale = 3, Fps = frameRate };
                    string path = Path.Combine(root, "settings.xml"); settings.Save(path); var loaded = Settings.Load(path);
                    Assert(loaded.Fps == frameRate && loaded.Scale == 3 && loaded.Width == 3840, "Settings did not persist");
                    var launch = loaded.Arguments(root);
                    Assert(launch.Contains("--draw_resolution_scale_x=3") && launch.Contains("--resolution=720p"), "Incorrect scaling arguments");
                    Assert(launch.Contains("--render_target_path_d3d12=rov") && launch.Contains("--psu_movie_present=true"), "Lost cutscene fixes");
                    Assert(launch.All(a => a.StartsWith("--") && a.Contains("=")), "Ambiguous late GPU argument");
                }
                Reject(() => new Settings { Fps = 999 }.Validate(), "Accepted invalid FPS");
                var dpiArgs = new Settings { Width = 3840, Height = 2160, Scale = 3 }.Arguments(root, 144, 3840, 2160);
                Assert(dpiArgs.Contains("--window_width=2560") && dpiArgs.Contains("--window_height=1440"), "DPI conversion changes pixel resolution");
                var fitted = new Settings { Width = 3840, Height = 2160, Scale = 3, Fullscreen = false }.Arguments(root, 144, 1920, 1080);
                Assert(fitted.Contains("--window_width=1280") && fitted.Contains("--draw_resolution_scale_x=3"), "Fitting the window changed internal render scale");
                foreach (int unsupported in new[] {30, 120, 0}) Reject(() => new Settings { Fps = unsupported }.Validate(), "Accepted unverified simulation rate");
                var defaults = new Settings().Arguments(root);
                Assert(defaults.Contains("--fullscreen=true") && defaults.Contains("--fullscreen_exclusive=false"), "Default is not borderless");
                Assert(defaults.Contains("--vsync=true") && defaults.Contains("--video_mode_refresh_rate=60") && defaults.Contains("--psu_max_fps=0"), "Unsafe gameplay clock defaults");
                Assert(defaults.Contains("--psu_unlock_extra_mode=true"), "Extra Mode is not available by default");
                string extraSettings = Path.Combine(root, "extra-settings.xml");
                new Settings { UnlockExtraMode = false }.Save(extraSettings);
                Assert(Settings.Load(extraSettings).Arguments(root).Contains("--psu_unlock_extra_mode=false"), "Original Extra Mode rules did not persist");
                File.WriteAllText(extraSettings, "<Settings><Width>1920</Width><Height>1080</Height><Scale>2</Scale><Fps>60</Fps></Settings>");
                Assert(Settings.Load(extraSettings).UnlockExtraMode, "Older settings did not enable the new Extra Mode default");
                Assert(Settings.Quote("a b\\") == "\"a b\\\\\"", "Trailing slash quoting");
                Assert(Settings.Quote("a\"b") == "\"a\\\"b\"", "Embedded quote escaping");
                string untouched = Path.Combine(root, "existing"); Directory.CreateDirectory(untouched); File.WriteAllText(Path.Combine(untouched, "keep"), "keep");
                bool existingRejected = false;
                try { Installer.Install(valid, untouched, new Settings(), false, (p,s) => {}, CancellationToken.None); } catch (IOException) { existingRejected = true; }
                Assert(existingRejected && File.ReadAllText(Path.Combine(untouched, "keep")) == "keep", "Existing destination changed");
                string invalidTarget = Path.Combine(root, "invalid-game");
                Reject(() => Installer.Install(valid, invalidTarget, new Settings(), false, (p,s) => {}, CancellationToken.None), "Invalid ISO installed");
                Assert(!Directory.Exists(invalidTarget), "Invalid ISO left an install");
                Reject(() => GameIcon.FromXex(new byte[24]), "Accepted an unsupported icon source");
                if (args.Length == 1) {
                    using (var disc = new DiscImage(args[0])) {
                        byte[] executable = disc.ReadGameExecutable(); Assert(disc.ExtractedSize > 1024 * 1024, "Real disc was empty");
                        byte[] iconBytes = GameIcon.FromXex(executable);
                        using (var stream = new MemoryStream(iconBytes)) using (var icon = new System.Drawing.Icon(stream))
                            Assert(icon.Width == 64 && icon.Height == 64, "Official icon does not load in Windows");
                        using (var hash = System.Security.Cryptography.SHA256.Create())
                            Assert(DiscImage.Hex(hash.ComputeHash(iconBytes.Skip(22).ToArray())) == GameIcon.PngHash, "Icon altered the official artwork");
                    }
                    var cancel = new CancellationTokenSource(); bool cancelled = false;
                    string target = Path.Combine(root, "cancelled");
                    try { Installer.Install(args[0], target, new Settings(), false, (p,s) => { if (p >= 4) cancel.Cancel(); }, cancel.Token); } catch (OperationCanceledException) { cancelled = true; }
                    Assert(cancelled && !Directory.Exists(target) && Directory.GetDirectories(root, ".psu-install-*").Length == 0, "Cancellation did not roll back");
                }
                Console.WriteLine("PASS: " + checks + " release checks"); return 0;
            } catch (Exception ex) { Console.Error.WriteLine(ex); return 1; }
            finally { if (Path.GetFullPath(root).StartsWith(Path.GetFullPath(Path.GetTempPath()), StringComparison.OrdinalIgnoreCase) && Path.GetFileName(root).StartsWith("psu-release-tests-")) Directory.Delete(root, true); }
        }
    }
}
