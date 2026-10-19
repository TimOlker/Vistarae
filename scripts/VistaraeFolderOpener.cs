using System;
using System.Diagnostics;
using System.IO;
using System.Text.RegularExpressions;
using System.Reflection;

[assembly: AssemblyTitle("Vistarae Folder Opener")]
[assembly: AssemblyProduct("Vistarae Travel Platform")]
[assembly: AssemblyDescription("Opens local and network photo folders in Windows File Explorer")]
[assembly: AssemblyCompany("Vistarae")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

namespace Vistarae
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            if (args == null || args.Length == 0) return;
            string rawUri = args[0];
            if (string.IsNullOrWhiteSpace(rawUri)) return;

            try
            {
                // Strip scheme prefix (e.g. vistarae-folder:// or vistarae-folder:)
                string uri = Regex.Replace(rawUri, @"^[a-zA-Z0-9_\-]+:\/{0,2}", "");
                
                // URL decode (handles %20, %5C, %27, etc.)
                string decoded = Uri.UnescapeDataString(uri);

                string folder = "";
                // Case A: UNC path starting with \\ or //
                Match uncMatch = Regex.Match(decoded, @"^[\\/]{2}(.+)$");
                if (uncMatch.Success)
                {
                    folder = @"\\" + uncMatch.Groups[1].Value.Replace('/', '\\');
                }
                // Case B: Local drive letter like C:\path or /C:/path
                else if (Regex.IsMatch(decoded, @"^[\\/]*[a-zA-Z]:"))
                {
                    folder = Regex.Replace(decoded, @"^[\\/]*([a-zA-Z]:.*)$", "$1").Replace('/', '\\');
                }
                // Case C: Bare IP address like 192.168.2.50\homes\...
                else if (Regex.IsMatch(decoded, @"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"))
                {
                    folder = @"\\" + decoded.Replace('/', '\\');
                }
                // Case D: Fallback
                else
                {
                    folder = decoded.Replace('/', '\\');
                }

                if (folder.Length > 3)
                {
                    folder = folder.TrimEnd('\\');
                }

                Process.Start("explorer.exe", "\"" + folder + "\"");
            }
            catch
            {
                // Suppress errors to prevent dialog popups
            }
        }
    }
}
