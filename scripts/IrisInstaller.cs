using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Threading;
using System.Windows.Forms;

namespace IrisInstaller
{
    public class InstallerForm : Form
    {
        private ProgressBar progressBar;
        private Label lblStatus;
        private Label lblTitle;
        private Label lblSub;
        private BackgroundWorker worker;

        public InstallerForm()
        {
            InitializeComponent();
            StartInstallation();
        }

        private void InitializeComponent()
        {
            this.Text = "Iris Voice Assistant Setup";
            this.ClientSize = new Size(440, 200);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterScreen;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.BackColor = Color.FromArgb(15, 23, 42); // slate-900
            this.ForeColor = Color.White;

            lblTitle = new Label
            {
                Text = "⚡ Iris Voice Assistant",
                Font = new Font("Segoe UI", 14, FontStyle.Bold),
                ForeColor = Color.FromArgb(56, 189, 248), // cyan/blue
                Location = new Point(24, 20),
                AutoSize = true
            };

            lblSub = new Label
            {
                Text = "Desktop Floating Orb Setup • Offline Speech Engine",
                Font = new Font("Segoe UI", 9, FontStyle.Regular),
                ForeColor = Color.FromArgb(148, 163, 184),
                Location = new Point(26, 50),
                AutoSize = true
            };

            progressBar = new ProgressBar
            {
                Location = new Point(26, 85),
                Size = new Size(388, 22),
                Style = ProgressBarStyle.Marquee,
                MarqueeAnimationSpeed = 25
            };

            lblStatus = new Label
            {
                Text = "Initializing Iris Floating Orb setup...",
                Font = new Font("Segoe UI", 9, FontStyle.Regular),
                ForeColor = Color.FromArgb(203, 213, 225),
                Location = new Point(26, 120),
                Size = new Size(388, 40)
            };

            this.Controls.Add(lblTitle);
            this.Controls.Add(lblSub);
            this.Controls.Add(progressBar);
            this.Controls.Add(lblStatus);

            worker = new BackgroundWorker();
            worker.DoWork += Worker_DoWork;
            worker.RunWorkerCompleted += Worker_RunWorkerCompleted;
        }

        private void StartInstallation()
        {
            this.Shown += (s, e) => worker.RunWorkerAsync();
        }

        private string FindIrisExe(string dir)
        {
            if (string.IsNullOrEmpty(dir) || !Directory.Exists(dir)) return null;

            string direct = Path.Combine(dir, "Iris-Orb.exe");
            if (File.Exists(direct)) return direct;

            string nested = Path.Combine(dir, "Iris-Orb", "Iris-Orb.exe");
            if (File.Exists(nested)) return nested;

            string packaged = Path.Combine(dir, "Orb-Package", "Iris-Orb.exe");
            if (File.Exists(packaged)) return packaged;

            try
            {
                string[] files = Directory.GetFiles(dir, "Iris-Orb.exe", SearchOption.AllDirectories);
                if (files.Length > 0) return files[0];
            }
            catch { }

            return null;
        }

        private void Worker_DoWork(object sender, DoWorkEventArgs e)
        {
            try
            {
                string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                string installDir = Path.Combine(localAppData, "IrisVoiceAssistant");

                // 1. Check if Iris Orb already exists in install directory
                string existingExe = FindIrisExe(installDir);
                if (!string.IsNullOrEmpty(existingExe) && File.Exists(existingExe))
                {
                    UpdateStatus("Existing Iris Orb installation found. Launching...");
                    LaunchOrb(existingExe);
                    return;
                }

                // 2. Check if running inside development repository
                string currentDir = AppDomain.CurrentDomain.BaseDirectory;
                string repoOrb = FindIrisExe(currentDir);
                if (string.IsNullOrEmpty(repoOrb))
                {
                    try
                    {
                        string parent = Path.GetFullPath(Path.Combine(currentDir, ".."));
                        repoOrb = FindIrisExe(parent);
                        if (string.IsNullOrEmpty(repoOrb))
                        {
                            string grandParent = Path.GetFullPath(Path.Combine(currentDir, "..", ".."));
                            repoOrb = FindIrisExe(grandParent);
                        }
                    }
                    catch { }
                }

                if (!string.IsNullOrEmpty(repoOrb) && File.Exists(repoOrb))
                {
                    UpdateStatus("Found local Iris Orb build. Launching...");
                    LaunchOrb(repoOrb);
                    return;
                }

                // 3. Extract embedded package to LocalAppData
                UpdateStatus("Extracting Iris Orb runtime to LocalAppData...");
                Directory.CreateDirectory(installDir);

                Assembly asm = Assembly.GetExecutingAssembly();
                string resourceName = null;
                foreach (string name in asm.GetManifestResourceNames())
                {
                    if (name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase))
                    {
                        resourceName = name;
                        break;
                    }
                }

                if (!string.IsNullOrEmpty(resourceName))
                {
                    string tempZip = Path.Combine(Path.GetTempPath(), "Iris-Orb-Setup-" + Guid.NewGuid().ToString("N") + ".zip");
                    using (Stream resStream = asm.GetManifestResourceStream(resourceName))
                    using (FileStream fs = new FileStream(tempZip, FileMode.Create, FileAccess.Write))
                    {
                        resStream.CopyTo(fs);
                    }

                    UpdateStatus("Decompressing runtime packages...");
                    ZipFile.ExtractToDirectory(tempZip, installDir);

                    try { File.Delete(tempZip); } catch { }

                    string targetExe = FindIrisExe(installDir);
                    if (!string.IsNullOrEmpty(targetExe) && File.Exists(targetExe))
                    {
                        CreateDesktopShortcut(targetExe);
                        UpdateStatus("Starting Iris Floating Orb...");
                        LaunchOrb(targetExe);
                    }
                    else
                    {
                        MessageBox.Show("Could not find Iris-Orb.exe after extraction.", "Iris Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    }
                }
                else
                {
                    string localZip = Path.Combine(currentDir, "Iris-Orb-Windows-v1.0.0.zip");
                    if (File.Exists(localZip))
                    {
                        UpdateStatus("Extracting local zip bundle...");
                        ZipFile.ExtractToDirectory(localZip, installDir);
                        string targetExe = FindIrisExe(installDir);
                        if (!string.IsNullOrEmpty(targetExe))
                        {
                            CreateDesktopShortcut(targetExe);
                            LaunchOrb(targetExe);
                        }
                    }
                    else
                    {
                        MessageBox.Show(
                            "Setup resource bundle could not be found.\n\nPlease run 'npm run orb' in terminal or download the standalone bundle.",
                            "Iris Setup", MessageBoxButtons.OK, MessageBoxIcon.Warning
                        );
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("Installation encountered an issue: " + ex.Message, "Iris Setup Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void UpdateStatus(string message)
        {
            if (this.InvokeRequired)
            {
                this.BeginInvoke(new Action(() => lblStatus.Text = message));
            }
            else
            {
                lblStatus.Text = message;
            }
        }

        private void LaunchOrb(string exePath)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = exePath,
                    WorkingDirectory = Path.GetDirectoryName(exePath),
                    UseShellExecute = true
                };
                Process.Start(psi);
                Thread.Sleep(1200);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to start Iris Orb: " + ex.Message, "Iris Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void CreateDesktopShortcut(string targetExe)
        {
            try
            {
                string desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                string shortcutPath = Path.Combine(desktopPath, "Iris Voice Assistant.lnk");

                Type shellType = Type.GetTypeFromProgID("WScript.Shell");
                if (shellType != null)
                {
                    dynamic shell = Activator.CreateInstance(shellType);
                    dynamic shortcut = shell.CreateShortcut(shortcutPath);
                    shortcut.TargetPath = targetExe;
                    shortcut.WorkingDirectory = Path.GetDirectoryName(targetExe);
                    shortcut.Description = "Iris Desktop Floating Voice Assistant (Ctrl+Shift+Space to toggle)";
                    shortcut.Save();
                }
            }
            catch
            {
                // Non-critical, ignore if shortcut creation fails
            }
        }

        private void Worker_RunWorkerCompleted(object sender, RunWorkerCompletedEventArgs e)
        {
            this.Close();
        }

        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new InstallerForm());
        }
    }
}
