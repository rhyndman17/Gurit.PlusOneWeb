using System;
using System.Diagnostics;
using System.IO;

public static class PlusOneWebLauncher
{
    public static void LaunchPlusOneWeb(string site)
    {
        LaunchPlusOneWebExe(site, @"C:\Program Files (x86)\Microsoft Dynamics\PlusOne\PlusOneWeb.exe");
    }

    public static void LaunchPlusOneWebExe(string site, string exePath)
    {
        string normalizedSite = (site ?? string.Empty).Trim().ToUpperInvariant();
        if (normalizedSite != "NZ" && normalizedSite != "AU")
        {
            throw new ArgumentException("Site must be NZ or AU.", nameof(site));
        }

        if (string.IsNullOrWhiteSpace(exePath) || !File.Exists(exePath))
        {
            throw new FileNotFoundException("PlusOne web executable was not found.", exePath);
        }

        string appFolder = Path.GetDirectoryName(exePath);
        string configPath = Path.Combine(appFolder, "PlusOneConfig.json");
        if (!File.Exists(configPath))
        {
            throw new FileNotFoundException("PlusOne configuration file was not found.", configPath);
        }

        var psi = new ProcessStartInfo
        {
            FileName = exePath,
            Arguments = $"--config \"{configPath}\" --host 127.0.0.1 --port 8088 --site {normalizedSite} --user \"{Environment.UserName}\" --open-browser",
            WorkingDirectory = appFolder,
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden
        };

        Process.Start(psi);
    }

    public static void LaunchPlusOneWebScript(string site, string scriptPath)
    {
        string normalizedSite = (site ?? string.Empty).Trim().ToUpperInvariant();
        if (normalizedSite != "NZ" && normalizedSite != "AU")
        {
            throw new ArgumentException("Site must be NZ or AU.", nameof(site));
        }

        if (string.IsNullOrWhiteSpace(scriptPath) || !File.Exists(scriptPath))
        {
            throw new FileNotFoundException("PlusOne web launcher script was not found.", scriptPath);
        }

        var psi = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            Arguments = $"-ExecutionPolicy Bypass -File \"{scriptPath}\" -Site {normalizedSite}",
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden
        };

        Process.Start(psi);
    }
}
