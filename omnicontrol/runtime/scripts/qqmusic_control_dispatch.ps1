param(
  [Parameter(Mandatory = $true)]
  [string]$Method,
  [string]$CommandPath,
  [string]$AdvCommandPath
)

$ErrorActionPreference = "Stop"

$command = if ($CommandPath) {
  Get-Content -LiteralPath $CommandPath -Raw
} else {
  ""
}

$advCommand = if ($AdvCommandPath) {
  Get-Content -LiteralPath $AdvCommandPath -Raw
} else {
  ""
}

Add-Type @"
using System;
using System.Runtime.InteropServices;

[ComImport, Guid("10126174-A34C-4DA4-9B5A-B71DE87EDD34"), InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]
public interface IQQMusicCreator {
    [DispId(1)]
    void CreateInterface([In] ref Guid riid, [MarshalAs(UnmanagedType.IDispatch)] out object ppObject);

    [DispId(2)]
    [return: MarshalAs(UnmanagedType.IDispatch)]
    object WebCreateInterface([MarshalAs(UnmanagedType.BStr)] string bstrRiid);
}

[ComImport, Guid("6927992D-6A89-4549-8A32-95901BF5D920")]
public class QQMusicCreatorClass { }

[ComImport, Guid("B07CCA0D-7B19-4921-868C-46B6C837825D"), InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]
public interface IQQMusicControl {
    [DispId(4)]
    void SetProperty([MarshalAs(UnmanagedType.BStr)] string name, [MarshalAs(UnmanagedType.Struct)] object value);

    [DispId(10)]
    void Bind();

    [DispId(12)]
    [return: MarshalAs(UnmanagedType.Struct)]
    object ExecuteCommand([MarshalAs(UnmanagedType.BStr)] string cmd);

    [DispId(18)]
    [return: MarshalAs(UnmanagedType.Struct)]
    object CanWebExecCommand();

    [DispId(19)]
    [return: MarshalAs(UnmanagedType.Struct)]
    object WebExecCommand([MarshalAs(UnmanagedType.BStr)] string cmd);

    [DispId(23)]
    [return: MarshalAs(UnmanagedType.Struct)]
    object WebExecCommand2([MarshalAs(UnmanagedType.BStr)] string cmd, [MarshalAs(UnmanagedType.BStr)] string adv);
}

public static class QQMusicControlDispatch {
    public static object Invoke(string method, string command, string advCommand) {
        var creator = (IQQMusicCreator)Activator.CreateInstance(typeof(QQMusicCreatorClass));
        var control = (IQQMusicControl)creator.WebCreateInterface("IQQMusicControl");
        control.Bind();
        if (string.Equals(method, "CanWebExecCommand", StringComparison.Ordinal)) {
            return control.CanWebExecCommand();
        }
        if (string.Equals(method, "ExecuteCommand", StringComparison.Ordinal)) {
            return control.ExecuteCommand(command);
        }
        if (string.Equals(method, "WebExecCommand", StringComparison.Ordinal)) {
            return control.WebExecCommand(command);
        }
        if (string.Equals(method, "WebExecCommand2", StringComparison.Ordinal)) {
            return control.WebExecCommand2(command, advCommand ?? "");
        }
        throw new InvalidOperationException("Unsupported QQMusic control method: " + method);
    }
}
"@

try {
  $result = [QQMusicControlDispatch]::Invoke($Method, $command, $advCommand)
  if ($null -ne $result) {
    Write-Output ("RETURN=" + $result.ToString())
  }
} catch {
  Write-Error $_
  exit 1
}
