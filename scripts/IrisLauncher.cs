using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace IrisVoiceAssistant
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string projectRoot = baseDir;

                // Discover project root if running from downloads/ or subfolder
                if (File.Exists(Path.Combine(baseDir, "..", "assistant.py")))
                {
                    projectRoot = Path.GetFullPath(Path.Combine(baseDir, ".."));
                }
                else if (File.Exists(Path.Combine(baseDir, "assistant.py")))
                {
                    projectRoot = baseDir;
                }

                // 1. Direct packaged Iris-Orb.exe
                string orbExe = Path.Combine(projectRoot, "Orb-Package", "Iris-Orb.exe");
                if (!File.Exists(orbExe))
                {
                    orbExe = Path.Combine(baseDir, "Orb-Package", "Iris-Orb.exe");
                }
                if (!File.Exists(orbExe))
                {
                    orbExe = Path.Combine(baseDir, "Iris-Orb.exe");
                }

                if (File.Exists(orbExe))
                {
                    ProcessStartInfo psi = new ProcessStartInfo();
                    psi.FileName = orbExe;
                    psi.WorkingDirectory = Path.GetDirectoryName(orbExe);
                    psi.UseShellExecute = true;
                    Process.Start(psi);
                    return;
                }

                // 2. Launch via hidden npm runner (strictly no console window)
                string orbFolder = Path.Combine(projectRoot, "Orb");
                if (Directory.Exists(orbFolder))
                {
                    ProcessStartInfo psi = new ProcessStartInfo();
                    psi.FileName = "cmd.exe";
                    psi.Arguments = "/c npm --prefix Orb start";
                    psi.WorkingDirectory = projectRoot;
                    psi.CreateNoWindow = true;
                    psi.WindowStyle = ProcessWindowStyle.Hidden;
                    psi.UseShellExecute = false;
                    Process.Start(psi);
                    return;
                }

                MessageBox.Show(
                    "Iris Desktop Orb could not find the Orb package in this directory.\n\nTip: You can also start it directly in your terminal using:\n  npm run orb",
                    "Iris Voice Assistant",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information
                );
            }
            catch (Exception ex)
            {
                MessageBox.Show("Could not launch Iris Orb: " + ex.Message, "Iris Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }
}
