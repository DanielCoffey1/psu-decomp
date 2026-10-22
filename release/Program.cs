using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace PsuRelease {
    public static class Program {
        public const string Version = "0.1.0-preview.4";
        [STAThread] public static int Main(string[] args) {
            try {
                // Headless installation uses the same validation and transactional path as the UI.
                if (args.Length > 0 && args[0] == "--install") {
                    if (args.Length < 3 || args.Length > 4 || (args.Length == 4 && args[3] != "--shortcut")) throw new ArgumentException("Usage: --install ISO NEW_FOLDER [--shortcut]");
                    string warning = Installer.Install(args[1], args[2], new Settings(), args.Length == 4, (p, s) => {}, CancellationToken.None);
                    File.WriteAllText(Path.Combine(args[2], "install-result.txt"), warning.Length == 0 ? "Installation verified." : warning); return 0;
                }
                if (args.Length == 2 && args[0] == "--verify-iso") { using (var disc = new DiscImage(args[1])) disc.VerifyGame(); return 0; }
                if (args.Length == 1 && args[0] == "--refresh-icon") {
                    string root = AppDomain.CurrentDomain.BaseDirectory;
                    GameIcon.Install(root); Installer.RefreshShortcutIcons(root); return 0;
                }
                bool forceSettings = args.Length == 1 && args[0] == "--settings";
                if (args.Length > 0 && !forceSettings) throw new ArgumentException("Unknown command-line option.");
                Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
#if INSTALLER
                Application.Run(new MainForm(true));
#else
                string startupError = null;
                try {
                    var saved = Settings.Load(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "settings.xml"));
                    if (saved.SkipLauncher && !forceSettings && (Control.ModifierKeys & Keys.Shift) == 0) {
                        using (var game = GameLauncher.Start(AppDomain.CurrentDomain.BaseDirectory, saved)) {}
                        return 0;
                    }
                } catch (Exception ex) { startupError = "Could not start with saved settings: " + ex.Message; }
                Application.Run(new MainForm(false, startupError));
#endif
                return 0;
            } catch (Exception ex) {
                if (args.Length != 0) { File.WriteAllText(Path.Combine(Path.GetTempPath(), "psu-install-error-" + Process.GetCurrentProcess().Id + ".txt"), ex.ToString()); }
                else MessageBox.Show(ex.Message, "PSU Recompiled", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
        }
    }

    public sealed class MainForm : Form {
        readonly bool installing;
        readonly string root = AppDomain.CurrentDomain.BaseDirectory;
        readonly TextBox iso = new TextBox(), folder = new TextBox();
        readonly ComboBox resolution = new ComboBox(), scale = new ComboBox(), fps = new ComboBox();
        readonly CheckBox fullscreen = new CheckBox(), keyboard = new CheckBox(), extraMode = new CheckBox(), skipLauncher = new CheckBox(), shortcut = new CheckBox();
        readonly Button primary = new Button(), cancel = new Button();
        readonly Label status = new Label(); readonly ProgressBar progress = new ProgressBar();
        readonly TableLayoutPanel body = new TableLayoutPanel();
        CancellationTokenSource cancellation;
        Process game;
        bool busy;
        public MainForm(bool install, string startupError = null) {
            SuspendLayout();
            installing = install; Text = install ? "PSU Recompiled — Install" : "PSU Recompiled — Launcher";
            string iconPath = Path.Combine(root, GameIcon.FileName);
            if (!install && File.Exists(iconPath)) using (var icon = new Icon(iconPath)) Icon = (Icon)icon.Clone();
            AutoScaleDimensions = new SizeF(96, 96); AutoScaleMode = AutoScaleMode.Dpi;
            Font = new Font("Segoe UI", 10); StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(760, install ? 720 : 650); MinimumSize = new Size(650, 500);
            BackColor = Color.FromArgb(247, 249, 252);
            body.Dock = DockStyle.Fill; body.Padding = new Padding(25); body.ColumnCount = 3;
            body.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize)); body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); body.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            body.AutoScroll = true; Controls.Add(body);
            Wide(new Label { Text = "PHANTASY STAR UNIVERSE", Font = new Font("Segoe UI", 19, FontStyle.Bold), ForeColor = Color.FromArgb(22, 48, 78), AutoSize = true }, 43);
            Wide(new Label { Text = "RECOMPILED  /  " + Program.Version + "  /  Windows x64", AutoSize = true, ForeColor = Color.DimGray }, 30);
            if (install) {
                Wide(new Label { Text = "Choose your Xbox 360 ISO, then install. Game data stays on your PC.\nNo compiler, disc mounting or administrator access required.", AutoSize = true }, 50);
                AddBrowse("Game ISO", iso, true); AddBrowse("Install folder", folder, false);
                folder.Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "PSU Recompiled");
            }
            resolution.Items.AddRange(new object[] { "1280 × 720", "1920 × 1080", "2560 × 1440", "3840 × 2160 (4K)" });
            scale.Items.AddRange(new object[] { "1× — original rendering", "2× — up to 1440p", "3× — up to 4K" });
            fps.Items.AddRange(new object[] { "60 FPS — normal game speed" });
            foreach (var combo in new[] { resolution, scale, fps }) { combo.DropDownStyle = ComboBoxStyle.DropDownList; combo.Dock = DockStyle.Fill; }
            AddRow("Window resolution", resolution, 40); AddRow("Render scale", scale, 40); AddRow("Frame limit", fps, 40);
            fullscreen.Text = "Borderless windowed (fills the desktop)"; keyboard.Text = "Enable keyboard controls (controllers also supported)";
            extraMode.Text = "Unlock Extra Mode and story-gated missions";
            shortcut.Text = "Create a desktop shortcut"; shortcut.Checked = true;
            foreach (var check in new[] { fullscreen, keyboard, extraMode }) { check.AutoSize = true; Wide(check, 31); }
            if (install) { shortcut.AutoSize = true; Wide(shortcut, 31); }
            else {
                skipLauncher.Text = "Skip launcher next time (use saved settings)"; skipLauncher.AutoSize = true; Wide(skipLauncher, 31);
                Wide(new Label { Text = "To change settings later, open PSU Settings in the installation folder,\nor hold Shift while opening your desktop shortcut.", AutoSize = true, ForeColor = Color.DimGray }, 50);
            }
            Wide(new Label { Text = "4K rendering uses 3× scale. Movies retain their original resolution.\n120 FPS / unlocked are unavailable: testing showed sped-up gameplay.", AutoSize = true, ForeColor = Color.FromArgb(80, 86, 96) }, 50);
            progress.Dock = DockStyle.Fill; progress.Visible = install; Wide(progress, install ? 22 : 0);
            status.AutoSize = true; status.MaximumSize = new Size(620, 0); Wide(status, 50);
            var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, FlowDirection = FlowDirection.RightToLeft, WrapContents = false };
            primary.Text = install ? "Install game" : "Save & Play"; primary.Size = new Size(150, 38);
            cancel.Text = install ? "Close" : "Save settings"; cancel.Size = new Size(135, 38);
            primary.AutoSize = true; cancel.AutoSize = true;
            actions.Controls.Add(primary); actions.Controls.Add(cancel); Wide(actions, 48);
            resolution.SelectedIndexChanged += (s, e) => { if (resolution.SelectedIndex >= 0) scale.SelectedIndex = resolution.SelectedIndex == 0 ? 0 : resolution.SelectedIndex == 3 ? 2 : 1; };
            Settings value = new Settings();
            if (!install) { try { value = Settings.Load(Path.Combine(root, "settings.xml")); } catch (Exception ex) { status.Text = "Settings reset: " + ex.Message; } }
            resolution.SelectedIndex = Array.IndexOf(Settings.Widths, value.Width); scale.SelectedIndex = value.Scale - 1;
            fps.SelectedIndex = Array.IndexOf(Settings.FrameRates, value.Fps); fullscreen.Checked = value.Fullscreen; keyboard.Checked = value.Keyboard;
            extraMode.Checked = value.UnlockExtraMode;
            skipLauncher.Checked = value.SkipLauncher;
            if (startupError != null) status.Text = startupError;
            primary.Click += async (s, e) => { if (installing) await Install(); else Play(); };
            cancel.Click += (s, e) => {
                if (installing) { if (busy) { cancellation.Cancel(); status.Text = "Cancelling and removing temporary files..."; cancel.Enabled = false; } else Close(); }
                else { try { GetSettings().Save(Path.Combine(root, "settings.xml")); status.Text = "Settings saved."; } catch (Exception ex) { Error(ex); } }
            };
            FormClosing += (s, e) => { if (busy && installing) { e.Cancel = true; cancellation.Cancel(); status.Text = "Cancelling and removing temporary files..."; } };
            ResumeLayout(true);
        }
        void Wide(Control control, int height) {
            int row = body.RowCount++; body.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            control.Margin = new Padding(3, 5, 3, 5);
            if (control is Label) {
                var label = (Label)control; label.AutoSize = true;
                body.SizeChanged += (s, e) => { label.MaximumSize = new Size(Math.Max(250, body.ClientSize.Width - body.Padding.Horizontal - 12), 0); };
            }
            if (control == status) control.MinimumSize = new Size(0, 42);
            if (control is ProgressBar) control.Height = 20;
            body.Controls.Add(control, 0, row); body.SetColumnSpan(control, 3);
        }
        void AddRow(string label, Control control, int height) {
            int row = body.RowCount++; body.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            control.Margin = new Padding(3, 5, 3, 5);
            body.Controls.Add(new Label { Text = label, AutoSize = true, Anchor = AnchorStyles.Left, Margin = new Padding(3, 6, 18, 6) }, 0, row); body.Controls.Add(control, 1, row);
            body.SetColumnSpan(control, 2);
        }
        void AddBrowse(string label, TextBox input, bool file) {
            int row = body.RowCount++; body.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            var browse = new Button { Text = "Browse...", AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, MinimumSize = new Size(95, 30), Anchor = AnchorStyles.Right, Margin = new Padding(3, 5, 3, 5) };
            input.Anchor = AnchorStyles.Left | AnchorStyles.Right; input.Margin = new Padding(3, 5, 3, 5);
            body.Controls.Add(new Label { Text = label, AutoSize = true, Anchor = AnchorStyles.Left, Margin = new Padding(3, 6, 18, 6) }, 0, row);
            body.Controls.Add(input, 1, row); body.Controls.Add(browse, 2, row);
            browse.Click += (s, e) => {
                if (file) { using (var dialog = new OpenFileDialog { Filter = "Xbox 360 ISO (*.iso)|*.iso|All files (*.*)|*.*", CheckFileExists = true }) if (dialog.ShowDialog(this) == DialogResult.OK) input.Text = dialog.FileName; }
                else { using (var dialog = new FolderBrowserDialog { Description = "Select a parent folder. A new PSU Recompiled folder will be created inside it." }) if (dialog.ShowDialog(this) == DialogResult.OK) input.Text = Path.Combine(dialog.SelectedPath, "PSU Recompiled"); }
            };
        }
        Settings GetSettings() { return new Settings { Width = Settings.Widths[resolution.SelectedIndex], Height = Settings.Heights[resolution.SelectedIndex], Scale = scale.SelectedIndex + 1, Fps = Settings.FrameRates[fps.SelectedIndex], Fullscreen = fullscreen.Checked, Keyboard = keyboard.Checked, UnlockExtraMode = extraMode.Checked, SkipLauncher = skipLauncher.Checked }; }
        void Error(Exception ex) { status.Text = ex.Message; MessageBox.Show(this, ex.Message, "PSU Recompiled", MessageBoxButtons.OK, MessageBoxIcon.Error); }
        async Task Install() {
            string source = iso.Text.Trim(), destination = folder.Text.Trim();
            if (!File.Exists(source) || destination.Length == 0) { status.Text = "Choose an ISO and installation folder first."; return; }
            var settings = GetSettings(); bool makeShortcut = shortcut.Checked; busy = true; cancellation = new CancellationTokenSource();
            foreach (Control child in body.Controls) child.Enabled = false;
            primary.Parent.Enabled = true; primary.Enabled = false; cancel.Enabled = true; cancel.Text = "Cancel"; progress.Enabled = true; status.Enabled = true;
            var report = new Progress<Tuple<int, string>>(p => { progress.Value = p.Item1; status.Text = p.Item2; });
            bool done = false;
            try {
                string warning = await Task.Run(() => Installer.Install(source, destination, settings, makeShortcut, (p, s) => ((IProgress<Tuple<int, string>>)report).Report(Tuple.Create(p, s)), cancellation.Token));
                done = true; status.Text = warning.Length == 0 ? "Installed. Open your desktop shortcut or the launcher to play." : warning;
            } catch (OperationCanceledException) { status.Text = "Installation cancelled. Your ISO was not changed."; }
              catch (Exception ex) { Error(ex); }
            finally {
                busy = false; cancellation.Dispose(); cancellation = null;
                foreach (Control child in body.Controls) child.Enabled = true;
                primary.Enabled = !done; cancel.Enabled = true; cancel.Text = "Close";
            }
            if (done) { primary.Text = "Installed"; Process.Start(new ProcessStartInfo(Path.Combine(destination, "PSU Launcher.exe")) { WorkingDirectory = destination, UseShellExecute = true }); }
        }
        void Play() {
            try {
                if (game != null && !game.HasExited) { status.Text = "The game is already running."; return; }
                var settings = GetSettings(); settings.Save(Path.Combine(root, "settings.xml"));
                if (game != null) { game.Dispose(); game = null; }
                game = GameLauncher.Start(root, settings);
                if (settings.SkipLauncher) { game.Dispose(); game = null; Close(); return; }
                game.Exited += (s, e) => { if (!IsDisposed && IsHandleCreated) BeginInvoke((Action)(() => { primary.Enabled = true; status.Text = game.ExitCode == 0 ? "Game closed. Your saves remain in Documents\\psu." : "Game exited with code " + game.ExitCode + ". See bin\\logs in your installation folder."; })); };
                primary.Enabled = false;
                status.Text = "Game running. Settings apply on the next launch.";
                game.EnableRaisingEvents = true;
            } catch (Exception ex) { primary.Enabled = true; Error(ex); }
        }
    }
}
