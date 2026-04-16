param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("invoke", "context", "events", "runtime")]
    [string]$Mode,
    [string]$Method = "",
    [string]$XmlPath = "",
    [int]$Version = 0,
    [UInt64]$QQUin = 0,
    [string]$Key = "",
    [string]$PlatformKey = "",
    [int]$LoginType = 0,
    [int]$DoLogin = 1,
    [int]$DoBind = 1,
    [int]$DoLoadPlayList = 0
)

$ErrorActionPreference = "Stop"

Add-Type @"
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using System.Runtime.InteropServices;
using System.Threading;

[ComImport, Guid("10126174-A34C-4DA4-9B5A-B71DE87EDD34"), InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]
public interface IQQMusicCreator
{
    [DispId(2)]
    [return: MarshalAs(UnmanagedType.IDispatch)]
    object WebCreateInterface([MarshalAs(UnmanagedType.BStr)] string bstrRiid);
}

[ComImport, Guid("6927992D-6A89-4549-8A32-95901BF5D920")]
public class QQMusicCreatorClass
{
}

[ComImport, Guid("B07CCA0D-7B19-4921-868C-46B6C837825D"), InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]
public interface IQQMusicControl
{
    [DispId(3)] object Login();
    [DispId(4)] void SetProperty([MarshalAs(UnmanagedType.BStr)] string bstrName, object vProperty);
    [DispId(5)] void GetProperty([MarshalAs(UnmanagedType.BStr)] string bstrName, out object pvProperty);
    [DispId(6)] void LoadPlayList();
    [DispId(10)] void Bind();
    [DispId(12)] object ExecuteCommand([MarshalAs(UnmanagedType.BStr)] string bstrCmd);
    [DispId(18)] int CanWebExecCommand();
    [DispId(19)] object WebExecCommand([MarshalAs(UnmanagedType.BStr)] string bstrCmd);
    [DispId(23)] object WebExecCommand2([MarshalAs(UnmanagedType.BStr)] string bstrCmd, [MarshalAs(UnmanagedType.BStr)] string bstrAdvCmd);
}

[ComImport, Guid("B196B284-BAB4-101A-B69C-00AA00341D07"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IConnectionPointContainerNative
{
    void EnumConnectionPoints(out IntPtr ppEnum);
    void FindConnectionPoint(ref Guid riid, [MarshalAs(UnmanagedType.Interface)] out IConnectionPointNative ppCP);
}

[ComImport, Guid("B196B286-BAB4-101A-B69C-00AA00341D07"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IConnectionPointNative
{
    void GetConnectionInterface(out Guid pIID);
    void GetConnectionPointContainer([MarshalAs(UnmanagedType.Interface)] out IConnectionPointContainerNative ppCPC);
    void Advise([MarshalAs(UnmanagedType.IUnknown)] object pUnkSink, out int pdwCookie);
    void Unadvise(int dwCookie);
    void EnumConnections(out IntPtr ppEnum);
}

[ComImport, Guid("E0044E80-24E6-401E-A45A-EFD702538ACA"), InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]
public interface IQQMusicControlEvents
{
    [DispId(1)] void OnLoginReply(ulong dwQQUin, string bstrKey, int lCode, string bstrErrDesc);
    [DispId(5)] void OnBindReply(ulong dwQQUin, int lCode);
    [DispId(8)] void OnServerMessage(string bstrSvrMsg);
    [DispId(9)] void OnPropertyChanged(string bstrName, object vProperty);
    [DispId(2)] void OnLogoutReply(ulong dwQQUin, int lCode);
    [DispId(3)] void OnDownloadReply(int lListType, int lCode, string bstrLocalPath);
    [DispId(4)] void OnUploadReply(int lListType, int lCode);
    [DispId(6)] void OnUnBindReply(ulong dwQQUin, int lCode);
    [DispId(7)] void OnExit(int lCode);
    [DispId(10)] void OnAddLoveList(int nErrorCode, int nType, int dwMusicID, string bstrURL);
    [DispId(11)] void OnDelLoveList(int nErrorCode, int nType, int dwMusicID, string bstrURL);
    [DispId(12)] void OnRefreshLoveList(int nErrorCode);
    [DispId(13)] void OnGetVIPInfo(int nErrorCode, object vVIPInfo);
    [DispId(14)] void OnQueryOnline(string bstrDoc);
}

[StructLayout(LayoutKind.Sequential)]
public struct POINT
{
    public int X;
    public int Y;
}

[StructLayout(LayoutKind.Sequential)]
public struct MSG
{
    public IntPtr hwnd;
    public uint message;
    public IntPtr wParam;
    public IntPtr lParam;
    public uint time;
    public POINT pt;
}

public static class MsgPump
{
    [DllImport("user32.dll")]
    public static extern bool PeekMessage(out MSG lpMsg, IntPtr hWnd, uint wMsgFilterMin, uint wMsgFilterMax, uint wRemoveMsg);

    [DllImport("user32.dll")]
    public static extern bool TranslateMessage([In] ref MSG lpMsg);

    [DllImport("user32.dll")]
    public static extern IntPtr DispatchMessage([In] ref MSG lpMsg);

    public const uint PM_REMOVE = 0x0001;

    public static void Pump(int milliseconds)
    {
        int steps = milliseconds / 50;
        if (steps < 1) steps = 1;
        for (int i = 0; i < steps; i++)
        {
            MSG msg;
            while (PeekMessage(out msg, IntPtr.Zero, 0, 0, PM_REMOVE))
            {
                TranslateMessage(ref msg);
                DispatchMessage(ref msg);
            }
            Thread.Sleep(50);
        }
    }
}

[ComVisible(true)]
[ClassInterface(ClassInterfaceType.None)]
public class QQMusicControlEventsSink : IQQMusicControlEvents
{
    public readonly List<string> Events = new List<string>();

    public void OnLoginReply(ulong dwQQUin, string bstrKey, int lCode, string bstrErrDesc)
    {
        Events.Add("OnLoginReply uin=" + dwQQUin + " code=" + lCode + " key=" + (bstrKey ?? "") + " err=" + (bstrErrDesc ?? ""));
    }

    public void OnBindReply(ulong dwQQUin, int lCode)
    {
        Events.Add("OnBindReply uin=" + dwQQUin + " code=" + lCode);
    }

    public void OnServerMessage(string bstrSvrMsg)
    {
        Events.Add("OnServerMessage " + (bstrSvrMsg ?? ""));
    }

    public void OnPropertyChanged(string bstrName, object vProperty)
    {
        Events.Add("OnPropertyChanged " + (bstrName ?? "") + "=" + (vProperty == null ? "<null>" : vProperty.ToString()));
    }

    public void OnLogoutReply(ulong dwQQUin, int lCode)
    {
        Events.Add("OnLogoutReply uin=" + dwQQUin + " code=" + lCode);
    }

    public void OnDownloadReply(int lListType, int lCode, string bstrLocalPath) { }
    public void OnUploadReply(int lListType, int lCode) { }
    public void OnUnBindReply(ulong dwQQUin, int lCode) { Events.Add("OnUnBindReply uin=" + dwQQUin + " code=" + lCode); }
    public void OnExit(int lCode) { Events.Add("OnExit code=" + lCode); }
    public void OnAddLoveList(int nErrorCode, int nType, int dwMusicID, string bstrURL) { }
    public void OnDelLoveList(int nErrorCode, int nType, int dwMusicID, string bstrURL) { }
    public void OnRefreshLoveList(int nErrorCode) { }
    public void OnGetVIPInfo(int nErrorCode, object vVIPInfo) { }
    public void OnQueryOnline(string bstrDoc) { }
}

public static class QQMusicControlEventHelper
{
    public static string[] Run(string xmlPath, bool doLogin, bool doBind, bool doLoadPlayList, int version, ulong qqUin, string key, string platformKey, int loginType)
    {
        List<string> lines = new List<string>();
        IQQMusicControl control = (IQQMusicControl)((IQQMusicCreator)new QQMusicCreatorClass()).WebCreateInterface("IQQMusicControl");
        if (version > 0) { try { control.SetProperty("QQMusicControlProperty_dwVersion", version); } catch { } }
        if (qqUin > 0) { try { control.SetProperty("QQMusicControlProperty_dwQQUin", qqUin); } catch { } }
        if (!string.IsNullOrEmpty(key)) { try { control.SetProperty("QQMusicControlProperty_strKey", key); } catch { } }
        if (!string.IsNullOrEmpty(platformKey)) { try { control.SetProperty("QQMusicControlProperty_strPlatformKey", platformKey); } catch { } }
        if (loginType > 0) { try { control.SetProperty("QQMusicControlProperty_nLoginType", loginType); } catch { } }

        IntPtr unk = Marshal.GetIUnknownForObject(control);
        try
        {
            Guid iidCpc = new Guid("B196B284-BAB4-101A-B69C-00AA00341D07");
            IntPtr ptr = IntPtr.Zero;
            int hr = Marshal.QueryInterface(unk, ref iidCpc, out ptr);
            lines.Add("QI=" + hr + " PTR=" + ptr.ToInt64());
            if (hr != 0 || ptr == IntPtr.Zero)
            {
                return lines.ToArray();
            }

            try
            {
                IConnectionPointContainerNative cpc = (IConnectionPointContainerNative)Marshal.GetTypedObjectForIUnknown(ptr, typeof(IConnectionPointContainerNative));
                Guid eventsIid = new Guid("E0044E80-24E6-401E-A45A-EFD702538ACA");
                IConnectionPointNative cp;
                cpc.FindConnectionPoint(ref eventsIid, out cp);
                lines.Add("FIND_OK");
                QQMusicControlEventsSink sink = new QQMusicControlEventsSink();
                int cookie;
                cp.Advise(sink, out cookie);
                lines.Add("ADVISE=" + cookie);
                try
                {
                    if (doLogin)
                    {
                        try { control.Login(); lines.Add("LOGIN_OK"); } catch (Exception ex) { lines.Add("LOGIN_ERR " + ex.Message); }
                        MsgPump.Pump(3000);
                    }
                    if (doBind)
                    {
                        try { control.Bind(); lines.Add("BIND_OK"); } catch (Exception ex) { lines.Add("BIND_ERR " + ex.Message); }
                        MsgPump.Pump(3000);
                    }
                    if (doLoadPlayList)
                    {
                        try { control.LoadPlayList(); lines.Add("LOADPLAYLIST_OK"); } catch (Exception ex) { lines.Add("LOADPLAYLIST_ERR " + ex.Message); }
                        MsgPump.Pump(2000);
                    }
                    if (!string.IsNullOrEmpty(xmlPath))
                    {
                        try { object ret = control.ExecuteCommand(System.IO.File.ReadAllText(xmlPath)); lines.Add("EXEC_RET " + (ret == null ? "<null>" : ret.ToString())); } catch (Exception ex) { lines.Add("EXEC_ERR " + ex.Message); }
                        MsgPump.Pump(3000);
                    }
                    object versionValue = null;
                    object uinValue = null;
                    object keyValue = null;
                    object platformValue = null;
                    object loginTypeValue = null;
                    object canWebValue = null;
                    try { control.GetProperty("QQMusicControlProperty_dwVersion", out versionValue); } catch { }
                    try { control.GetProperty("QQMusicControlProperty_dwQQUin", out uinValue); } catch { }
                    try { control.GetProperty("QQMusicControlProperty_strKey", out keyValue); } catch { }
                    try { control.GetProperty("QQMusicControlProperty_strPlatformKey", out platformValue); } catch { }
                    try { control.GetProperty("QQMusicControlProperty_nLoginType", out loginTypeValue); } catch { }
                    try { canWebValue = control.CanWebExecCommand(); } catch { }
                    lines.Add("CTX version=" + (versionValue == null ? "<null>" : versionValue.ToString())
                        + " uin=" + (uinValue == null ? "<null>" : uinValue.ToString())
                        + " key=" + (keyValue == null ? "<null>" : keyValue.ToString())
                        + " pkey=" + (platformValue == null ? "<null>" : platformValue.ToString())
                        + " loginType=" + (loginTypeValue == null ? "<null>" : loginTypeValue.ToString())
                        + " canWeb=" + (canWebValue == null ? "<null>" : canWebValue.ToString()));
                    lines.AddRange(sink.Events);
                }
                finally
                {
                    try { cp.Unadvise(cookie); } catch { }
                }
            }
            finally
            {
                Marshal.Release(ptr);
            }
        }
        finally
        {
            Marshal.Release(unk);
        }
        return lines.ToArray();
    }
}

public static class QQMusicRuntimeScanner
{
    [StructLayout(LayoutKind.Sequential)]
    public struct MEMORY_BASIC_INFORMATION
    {
        public IntPtr BaseAddress;
        public IntPtr AllocationBase;
        public uint AllocationProtect;
        public IntPtr RegionSize;
        public uint State;
        public uint Protect;
        public uint Type;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint processAccess, bool inheritHandle, int processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ReadProcessMemory(IntPtr hProcess, IntPtr lpBaseAddress, byte[] lpBuffer, int dwSize, out IntPtr lpNumberOfBytesRead);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern int VirtualQueryEx(IntPtr hProcess, IntPtr lpAddress, out MEMORY_BASIC_INFORMATION lpBuffer, int dwLength);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);

    private const uint PROCESS_QUERY_INFORMATION = 0x0400;
    private const uint PROCESS_VM_READ = 0x0010;
    private const uint MEM_COMMIT = 0x1000;
    private const uint PAGE_GUARD = 0x100;
    private const uint PAGE_NOACCESS = 0x01;

    private static bool IsReadable(uint protect)
    {
        uint code = protect & 0xFF;
        return code == 0x02 || code == 0x04 || code == 0x08 || code == 0x10 || code == 0x20 || code == 0x40 || code == 0x80;
    }

    public static Dictionary<string, string> Scan(int processId)
    {
        Dictionary<string, string> result = new Dictionary<string, string>();
        IntPtr handle = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, false, processId);
        if (handle == IntPtr.Zero)
        {
            return result;
        }

        try
        {
            long address = 0;
            while (address < 0x7FFFFFFF)
            {
                MEMORY_BASIC_INFORMATION mbi;
                int queried = VirtualQueryEx(handle, new IntPtr(address), out mbi, Marshal.SizeOf(typeof(MEMORY_BASIC_INFORMATION)));
                if (queried == 0)
                {
                    break;
                }

                long baseAddress = mbi.BaseAddress.ToInt64();
                long regionSize = mbi.RegionSize.ToInt64();
                if (mbi.State == MEM_COMMIT && (mbi.Protect & PAGE_GUARD) == 0 && (mbi.Protect & PAGE_NOACCESS) == 0 && IsReadable(mbi.Protect) && regionSize > 0 && regionSize <= 2 * 1024 * 1024)
                {
                    byte[] buffer = new byte[(int)regionSize];
                    IntPtr bytesRead;
                    if (ReadProcessMemory(handle, new IntPtr(baseAddress), buffer, buffer.Length, out bytesRead) && bytesRead.ToInt64() > 0)
                    {
                        string text = System.Text.Encoding.GetEncoding(28591).GetString(buffer, 0, (int)bytesRead.ToInt64());
                        MatchCollection matches = Regex.Matches(
                            text,
                            @"(?<name>qqmusic_uin|qqmusic_key|qqmusic_gkey|qqmusic_guid|qqmusic_miniversion|qqmusic_version|tmeLoginType|uid|qm_hideuin|qm_method|psrf_qqopenid|psrf_qqrefresh_token|psrf_qqunionid|qm_keyst|authst)\s*=\s*(?<value>[^;\r\n\s]+)",
                            RegexOptions.Singleline
                        );
                        foreach (Match item in matches)
                        {
                            if (!item.Success) continue;
                            string name = item.Groups["name"].Value;
                            string value = item.Groups["value"].Value;
                            if (!string.IsNullOrEmpty(name) && !string.IsNullOrEmpty(value) && !result.ContainsKey(name))
                            {
                                result[name] = value;
                            }
                        }
                        if (result.ContainsKey("qqmusic_uin") && result.ContainsKey("qqmusic_key"))
                        {
                            return result;
                        }
                    }
                }
                address = baseAddress + Math.Max(regionSize, 0x1000);
            }
        }
        finally
        {
            CloseHandle(handle);
        }
        return result;
    }
}
"@

function New-QQMusicControlSession {
    $creator = New-Object -ComObject QQMusicSvr.QQMusicCreator
    $control = $creator.WebCreateInterface("IQQMusicControl")
    return @{
        creator = $creator
        control = $control
    }
}

function Set-QQMusicControlContext {
    param(
        [Parameter(Mandatory = $true)]$Control
    )
    if ($Version -gt 0) { try { $Control.SetProperty("QQMusicControlProperty_dwVersion", $Version) } catch {} }
    if ($QQUin -gt 0) { try { $Control.SetProperty("QQMusicControlProperty_dwQQUin", [UInt64]$QQUin) } catch {} }
    if ($Key) { try { $Control.SetProperty("QQMusicControlProperty_strKey", $Key) } catch {} }
    if ($PlatformKey) { try { $Control.SetProperty("QQMusicControlProperty_strPlatformKey", $PlatformKey) } catch {} }
    if ($LoginType -gt 0) { try { $Control.SetProperty("QQMusicControlProperty_nLoginType", $LoginType) } catch {} }
}

function Initialize-QQMusicControl {
    param(
        [Parameter(Mandatory = $true)]$Control
    )
    if ($DoLogin -ne 0) {
        try { [void]$Control.Login() } catch {}
    }
    if ($DoBind -ne 0) {
        try { [void]$Control.Bind() } catch {}
    }
    if ($DoLoadPlayList -ne 0) {
        try { [void]$Control.LoadPlayList() } catch {}
    }
}

$propertyNames = @(
    "QQMusicControlProperty_dwVersion",
    "QQMusicControlProperty_dwQQUin",
    "QQMusicControlProperty_strKey",
    "QQMusicControlProperty_strPlatformKey",
    "QQMusicControlProperty_nLoginType"
)

if ($Mode -eq "events") {
    $lines = [QQMusicControlEventHelper]::Run($XmlPath, ($DoLogin -ne 0), ($DoBind -ne 0), ($DoLoadPlayList -ne 0), $Version, [UInt64]$QQUin, $Key, $PlatformKey, $LoginType)
    [ordered]@{
        lines = @($lines)
    } | ConvertTo-Json -Depth 6 -Compress
    exit 0
}

if ($Mode -eq "runtime") {
    $proc = Get-Process QQMusic -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $proc) {
        [ordered]@{ error = "QQMusic process not found" } | ConvertTo-Json -Depth 6 -Compress
        exit 1
    }
    $data = [QQMusicRuntimeScanner]::Scan($proc.Id)
    $data | Add-Member -NotePropertyName process_id -NotePropertyValue $proc.Id
    $data | ConvertTo-Json -Depth 6 -Compress
    exit 0
}

$session = New-QQMusicControlSession
$control = $session.control
Set-QQMusicControlContext -Control $control
Initialize-QQMusicControl -Control $control

if ($Mode -eq "context") {
    $result = [ordered]@{}
    foreach ($name in $propertyNames) {
        $value = $null
        try { $control.GetProperty($name, [ref]$value) } catch {}
        $result[$name] = $value
    }
    $can = $null
    try { $can = $control.CanWebExecCommand() } catch {}
    $result["CanWebExecCommand"] = $can
    $result | ConvertTo-Json -Depth 6 -Compress
    exit 0
}

if ($Mode -eq "invoke") {
    $result = [ordered]@{
        method = $Method
        return_value = $null
    }
    try {
        if ($Method -eq "CanWebExecCommand") {
            $result["return_value"] = $control.CanWebExecCommand()
        } elseif ($Method -eq "WebExecCommand2") {
            $xml = Get-Content -LiteralPath $XmlPath -Raw
            $result["return_value"] = $control.WebExecCommand2($xml, "")
        } elseif ($Method -eq "WebExecCommand") {
            $xml = Get-Content -LiteralPath $XmlPath -Raw
            $result["return_value"] = $control.WebExecCommand($xml)
        } elseif ($Method -eq "ExecuteCommand") {
            $xml = Get-Content -LiteralPath $XmlPath -Raw
            $result["return_value"] = $control.ExecuteCommand($xml)
        } else {
            throw "Unsupported QQMusic helper method: $Method"
        }
        $result | ConvertTo-Json -Depth 6 -Compress
        exit 0
    } catch {
        [ordered]@{
            error = $_.Exception.Message
            method = $Method
        } | ConvertTo-Json -Depth 6 -Compress
        exit 1
    }
}
