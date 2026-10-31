using System;
using TMPro;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.UI;

/// <summary>
/// The first screen: the player's access code, the server address (behind "Advanced") and a Connect button.
/// Both values are saved on the device in PlayerPrefs. The code is the player's own: it is never built into the app.
///
/// Built entirely at runtime (no scene changes needed): installs itself after the scene loads when the scene has a
/// WebSocketManager, stops the socket from connecting on its own, and hides the title screen until the server accepts the code.
/// Typing uses an on-screen keyboard of plain Buttons, because the trigger clicker (XRUIClicker) presses Buttons only.
/// </summary>
public class AccessGate : MonoBehaviour
{
    // The public address of the interview server. The hostname is not final yet: change it here only.
    public const string DefaultServer = "wss://quest.alearningmind.org/ws";
    // Tried after DefaultServer, only while the default address is in use: the project owner's own fallbacks, e.g. "ws://YOUR_TAILSCALE_IP:8765", "ws://YOUR_PC_LAN_IP:8765" (none in this repository).
    public static readonly string[] FallbackServers = { };

    private const string PrefCode = "vrsim.access_code";
    private const string PrefServer = "vrsim.server_address";

    /// True while the panel is up; InterviewFlow keeps the title screen hidden meanwhile.
    public static bool Showing { get; private set; }
    public static AccessGate Instance { get; private set; }

    private WebSocketManager webSocket;
    private GameObject canvasGo;
    private GameObject advancedRow;
    private TextMeshProUGUI codeText, serverText, statusText, advancedLabel, remainingText;
    private Image codeBox, serverBox;
    private Button connectButton;
    private string code = "", server = DefaultServer;
    private bool editingServer, advanced, connecting;
    private int remainingToday = -1;

    private static readonly Color Panel = new Color(0.06f, 0.08f, 0.12f, 0.96f);
    private static readonly Color Key = new Color(0.16f, 0.2f, 0.28f);
    private static readonly Color Accent = new Color(0.1f, 0.55f, 0.62f);
    private static readonly Color FieldOn = new Color(0.12f, 0.3f, 0.36f);
    private static readonly Color FieldOff = new Color(0.1f, 0.12f, 0.16f);

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
    private static void Prepare() => WebSocketManager.AutoConnect = false;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        var ws = FindObjectOfType<WebSocketManager>();
        if (ws == null) { WebSocketManager.AutoConnect = true; return; }
        if (Instance == null) new GameObject("AccessGate").AddComponent<AccessGate>();
    }

    /// The address list the socket should try for a saved address.
    public static string AddressesFor(string address)
    {
        address = NormalizeAddress(address);
        return address == DefaultServer ? DefaultServer + "," + string.Join(",", FallbackServers) : address;
    }

    /// "host:8765" -> "ws://host:8765"; anything already ws:// or wss:// is kept; blank -> the default.
    public static string NormalizeAddress(string address)
    {
        address = (address ?? "").Trim();
        if (address.Length == 0) return DefaultServer;
        if (address.StartsWith("ws://", StringComparison.OrdinalIgnoreCase) || address.StartsWith("wss://", StringComparison.OrdinalIgnoreCase))
            return address;
        return "ws://" + address;
    }

    // --- lifecycle ---------------------------------------------------------------------------------------------

    private void Awake()
    {
        Instance = this;
        webSocket = FindObjectOfType<WebSocketManager>();
        try
        {
            code = PlayerPrefs.GetString(PrefCode, "");
            server = PlayerPrefs.GetString(PrefServer, DefaultServer);
        }
        catch (Exception) { }
        if (string.IsNullOrEmpty(server)) server = DefaultServer;
        advanced = server != DefaultServer;
        BuildUi();
        if (webSocket != null)
        {
            webSocket.OnAuthAccepted += OnAccepted;
            webSocket.OnAuthRejected += OnRejected;
            webSocket.OnLimitReached += OnLimitReached;
        }
        Show(string.IsNullOrEmpty(code) ? "Type the access code you were given, then press Connect." : "Press Connect to sign in.");
    }

    private void OnDestroy()
    {
        if (webSocket != null)
        {
            webSocket.OnAuthAccepted -= OnAccepted;
            webSocket.OnAuthRejected -= OnRejected;
            webSocket.OnLimitReached -= OnLimitReached;
        }
        if (Instance == this) { Instance = null; Showing = false; }
    }

    private void Show(string status)
    {
        Showing = true;
        connecting = false;
        if (canvasGo != null) canvasGo.SetActive(true);
        var title = GameObject.Find("TitleCanvas");
        if (title != null) title.SetActive(false);
        SetStatus(status);
        Refresh();
    }

    private void Hide()
    {
        Showing = false;
        if (canvasGo != null) canvasGo.SetActive(false);
        var flow = FindObjectOfType<InterviewFlow>();
        if (flow != null && flow.CurrentPhase == InterviewFlow.Phase.Title) flow.ShowTitleScreen();
    }

    // --- actions --------------------------------------------------------------------------------------------

    /// Connect with the given values (the Connect button, and the editor test).
    public void Submit(string newCode, string newServer)
    {
        code = (newCode ?? "").Trim();
        server = NormalizeAddress(newServer);
        Submit();
    }

    private void Submit()
    {
        if (connecting) return;
        if (string.IsNullOrEmpty(code)) { SetStatus("Type your access code first."); return; }
        server = NormalizeAddress(server);
        try
        {
            PlayerPrefs.SetString(PrefCode, code);
            PlayerPrefs.SetString(PrefServer, server);
            PlayerPrefs.Save();
        }
        catch (Exception) { }
        connecting = true;
        SetStatus("Connecting to " + server + " ...");
        Refresh();
        Debug.Log("[AccessGate] connecting to " + server);   // never log the code
        if (webSocket != null) webSocket.Connect(AddressesFor(server), code);
    }

    private void OnAccepted(int remaining)
    {
        remainingToday = remaining;
        UpdateRemaining();
        Debug.Log("[AccessGate] signed in" + (remaining >= 0 ? ", " + remaining + " interviews left today" : ""));
        SetStatus(remaining >= 0 ? "Signed in. " + RemainingLine() : "Signed in.");
        connecting = false;
        Invoke(nameof(Hide), 1.2f);
    }

    private void OnRejected(string reason, string message)
    {
        Debug.Log("[AccessGate] refused: " + reason);
        CancelInvoke(nameof(Hide));
        string text = message;
        if (reason == "busy" && string.IsNullOrEmpty(text)) text = "Someone else is practising right now. Try again in a few minutes.";
        if (string.IsNullOrEmpty(text)) text = "The server refused the access code.";
        var flow = FindObjectOfType<InterviewFlow>();
        if (flow != null) flow.ReturnToTitle(null);
        Show(text + "\nCheck the code and press Connect to try again.");
    }

    private void OnLimitReached()
    {
        remainingToday = 0;
        UpdateRemaining();
    }

    /// Called by InterviewFlow when an interview begins, so the counter on the title screen stays roughly right.
    public static void NoteInterviewStarted()
    {
        if (Instance == null || Instance.remainingToday <= 0) return;
        Instance.remainingToday--;
        Instance.UpdateRemaining();
    }

    private string RemainingLine() => remainingToday == 1 ? "1 interview left today" : remainingToday + " interviews left today";

    private void UpdateRemaining()
    {
        if (remainingText == null)
        {
            // a small line at the bottom of the title screen
            var title = GameObject.Find("TitleCanvas");
            if (title == null) title = FindTitleCanvas();
            if (title == null) return;
            remainingText = MakeText(title.transform, "InterviewsLeft", "", 24f, new Color(0.7f, 0.85f, 0.9f), new Vector2(0f, -300f), new Vector2(900f, 36f));
        }
        remainingText.text = remainingToday >= 0 ? RemainingLine() : "";
    }

    private static GameObject FindTitleCanvas()
    {
        foreach (var c in Resources.FindObjectsOfTypeAll<Canvas>())
            if (c.name == "TitleCanvas" && c.gameObject.scene.IsValid()) return c.gameObject;
        return null;
    }

    private void Type(string key)
    {
        if (connecting) return;
        if (editingServer)
        {
            if (server.Length < 120) server += key.ToLowerInvariant();
        }
        else if (code.Length < 32) code += key.ToUpperInvariant();
        Refresh();
    }

    private void Backspace()
    {
        if (connecting) return;
        if (editingServer) { if (server.Length > 0) server = server.Substring(0, server.Length - 1); }
        else if (code.Length > 0) code = code.Substring(0, code.Length - 1);
        Refresh();
    }

    private void Clear()
    {
        if (connecting) return;
        if (editingServer) server = ""; else code = "";
        Refresh();
    }

    private void ToggleAdvanced()
    {
        advanced = !advanced;
        if (!advanced) editingServer = false;
        Refresh();
    }

    private void SetStatus(string text)
    {
        if (statusText != null) statusText.text = text;
    }

    private void Refresh()
    {
        if (codeText == null) return;
        codeText.text = code.Length > 0 ? code : "<color=#7f8a99>(type your code)</color>";
        serverText.text = server.Length > 0 ? server : "<color=#7f8a99>(blank = default)</color>";
        codeBox.color = editingServer ? FieldOff : FieldOn;
        serverBox.color = editingServer ? FieldOn : FieldOff;
        advancedRow.SetActive(advanced);
        advancedLabel.text = advanced ? "Advanced: on" : "Advanced";
        connectButton.interactable = !connecting;
    }

    // --- UI ---------------------------------------------------------------------------------------------------

    private void BuildUi()
    {
        // Same place as the title screen (which is hidden meanwhile), a little lower and smaller so the keyboard fits.
        Vector3 position = new Vector3(0f, 1.3f, 0.35f);
        Quaternion rotation = Quaternion.identity;
        var title = GameObject.Find("TitleCanvas");
        if (title != null) { position = title.transform.position + Vector3.down * 0.12f; rotation = title.transform.rotation; }

        canvasGo = new GameObject("AccessCanvas", typeof(RectTransform));
        canvasGo.layer = title != null ? title.layer : 0;
        var canvas = canvasGo.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.WorldSpace;
        canvas.worldCamera = Camera.main;
        canvasGo.AddComponent<CanvasScaler>().dynamicPixelsPerUnit = 3f;
        canvasGo.AddComponent<GraphicRaycaster>();
        canvasGo.AddComponent<TrackedDeviceGraphicRaycaster>();
        var rt = canvasGo.GetComponent<RectTransform>();
        rt.sizeDelta = new Vector2(1100f, 860f);
        rt.localScale = Vector3.one * 0.0013f;
        rt.position = position;
        rt.rotation = rotation;
        var root = canvasGo.transform;

        var bg = new GameObject("Background", typeof(RectTransform));
        bg.transform.SetParent(root, false);
        var bgImage = bg.AddComponent<Image>();
        bgImage.color = Panel;
        bgImage.raycastTarget = false;
        bg.GetComponent<RectTransform>().sizeDelta = new Vector2(1100f, 860f);

        MakeText(root, "Title", "Interview Practice: sign in", 44f, Color.white, new Vector2(0f, 385f), new Vector2(1000f, 60f)).fontStyle = FontStyles.Bold;

        // access code field
        MakeText(root, "CodeLabel", "Access code", 28f, new Color(0.75f, 0.8f, 0.88f), new Vector2(-400f, 305f), new Vector2(220f, 50f));
        codeBox = MakeField(root, "CodeField", new Vector2(110f, 305f), new Vector2(760f, 70f), out codeText, () => { editingServer = false; Refresh(); });

        // server address field (Advanced)
        advancedRow = new GameObject("AdvancedRow", typeof(RectTransform));
        advancedRow.transform.SetParent(root, false);
        MakeText(advancedRow.transform, "ServerLabel", "Server address", 26f, new Color(0.75f, 0.8f, 0.88f), new Vector2(-400f, 215f), new Vector2(220f, 50f));
        serverBox = MakeField(advancedRow.transform, "ServerField", new Vector2(40f, 215f), new Vector2(620f, 64f), out serverText, () => { editingServer = true; Refresh(); });
        serverText.fontSize = 26f;
        MakeButton(advancedRow.transform, "DefaultServer", "Default", 24f, new Vector2(430f, 215f), new Vector2(120f, 64f), Key, out _)
            .onClick.AddListener(() => { if (!connecting) { server = DefaultServer; Refresh(); } });

        // keyboard
        string[] rows = { "1234567890", "QWERTYUIOP", "ASDFGHJKL-", "ZXCVBNM.:/" };
        const float keyW = 92f, keyH = 72f, gap = 8f;
        for (int r = 0; r < rows.Length; r++)
        {
            float y = 120f - r * (keyH + gap);
            for (int c = 0; c < rows[r].Length; c++)
            {
                string k = rows[r][c].ToString();
                float x = (c - (rows[r].Length - 1) / 2f) * (keyW + gap);
                MakeButton(root, "Key_" + k, k, 34f, new Vector2(x, y), new Vector2(keyW, keyH), Key, out _).onClick.AddListener(() => Type(k));
            }
        }
        float bottomKeys = 120f - 4 * (keyH + gap);
        MakeButton(root, "Key_Back", "Delete", 28f, new Vector2(-300f, bottomKeys), new Vector2(240f, keyH), Key, out _).onClick.AddListener(Backspace);
        MakeButton(root, "Key_Clear", "Clear", 28f, new Vector2(-40f, bottomKeys), new Vector2(240f, keyH), Key, out _).onClick.AddListener(Clear);
        MakeButton(root, "Key_Underscore", "_", 34f, new Vector2(150f, bottomKeys), new Vector2(92f, keyH), Key, out _).onClick.AddListener(() => Type("_"));

        // bottom row
        MakeButton(root, "AdvancedToggle", "Advanced", 28f, new Vector2(-330f, -330f), new Vector2(300f, 90f), new Color(0.3f, 0.32f, 0.4f), out advancedLabel)
            .onClick.AddListener(ToggleAdvanced);
        connectButton = MakeButton(root, "StartInterview", "Connect", 40f, new Vector2(250f, -330f), new Vector2(460f, 90f), Accent, out _);
        connectButton.onClick.AddListener(Submit);   // named StartInterview so the clicker plays its confirm sound

        statusText = MakeText(root, "Status", "", 26f, new Color(0.95f, 0.85f, 0.55f), new Vector2(0f, -245f), new Vector2(1040f, 80f));
    }

    private static Image MakeField(Transform parent, string name, Vector2 pos, Vector2 size, out TextMeshProUGUI text, Action onClick)
    {
        var b = MakeButton(parent, name, "", 34f, pos, size, Color.white, out text);
        text.fontStyle = FontStyles.Normal;
        text.alignment = TextAlignmentOptions.MidlineLeft;
        text.margin = new Vector4(18f, 0f, 18f, 0f);
        text.enableWordWrapping = false;
        text.overflowMode = TextOverflowModes.Ellipsis;
        b.onClick.AddListener(() => onClick());
        var image = (Image)b.targetGraphic;
        b.transition = Selectable.Transition.None;
        return image;
    }

    private static TextMeshProUGUI MakeText(Transform parent, string name, string text, float fontSize, Color color, Vector2 pos, Vector2 box)
    {
        var go = new GameObject(name, typeof(RectTransform));
        go.transform.SetParent(parent, false);
        go.layer = parent.gameObject.layer;
        var t = go.AddComponent<TextMeshProUGUI>();
        t.text = text;
        t.fontSize = fontSize;
        t.color = color;
        t.alignment = TextAlignmentOptions.Center;
        t.enableWordWrapping = true;
        t.raycastTarget = false;
        t.rectTransform.sizeDelta = box;
        t.rectTransform.anchoredPosition = pos;
        return t;
    }

    private static Button MakeButton(Transform parent, string name, string label, float labelSize, Vector2 pos, Vector2 size, Color normal, out TextMeshProUGUI labelText)
    {
        var go = new GameObject(name, typeof(RectTransform));
        go.transform.SetParent(parent, false);
        go.layer = parent.gameObject.layer;
        var image = go.AddComponent<Image>();
        image.color = Color.white;
        var button = go.AddComponent<Button>();
        button.targetGraphic = image;
        var colors = button.colors;
        colors.normalColor = normal;
        colors.highlightedColor = Color.Lerp(normal, Color.white, 0.4f);
        colors.pressedColor = Color.Lerp(normal, Color.black, 0.35f);
        colors.selectedColor = normal;
        colors.disabledColor = new Color(0.35f, 0.35f, 0.38f, 0.8f);
        colors.fadeDuration = 0.08f;
        button.colors = colors;
        var rt = go.GetComponent<RectTransform>();
        rt.sizeDelta = size;
        rt.anchoredPosition = pos;
        labelText = MakeText(go.transform, "Label", label, labelSize, Color.white, Vector2.zero, size);
        labelText.fontStyle = FontStyles.Bold;
        return button;
    }

    // for the editor test
    public string StatusText => statusText != null ? statusText.text : "";
    public string RemainingText => remainingToday >= 0 ? RemainingLine() : "";
}
