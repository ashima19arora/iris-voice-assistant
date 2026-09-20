// ==============================================================================
// IRIS VOICE ASSISTANT - AWS CEDAR AUTHORIZATION POLICY
// ==============================================================================
// Cedar is the open-source authorization policy language developed by AWS.
// Every spoken command executed by Iris is evaluated against these policies.

// ------------------------------------------------------------------------------
// TIER 0 & TIER 1: PERMIT SAFE DIAGNOSTICS & USER CONTROLS
// ------------------------------------------------------------------------------
// Permit read-only system metrics, time, and knowledge Q&A
permit(
    principal == User::"VoiceUser",
    action in [
        Action::"SYSTEM_RAM",
        Action::"SYSTEM_BATTERY",
        Action::"SYSTEM_CPU",
        Action::"SYSTEM_TIME",
        Action::"SYSTEM_DATE",
        Action::"GREETING",
        Action::"KNOWLEDGE_QUERY"
    ],
    resource == Resource::"System"
);

// Permit standard browser actions and web navigation
permit(
    principal == User::"VoiceUser",
    action in [
        Action::"SEARCH_WEB",
        Action::"OPEN_WEBSITE",
        Action::"BROWSER_NEW_TAB",
        Action::"BROWSER_SWITCH_TAB",
        Action::"BROWSER_REFRESH",
        Action::"BROWSER_REOPEN_TAB",
        Action::"BROWSER_SCROLL_DOWN",
        Action::"BROWSER_SCROLL_UP",
        Action::"BROWSER_SCROLL_TOP",
        Action::"BROWSER_SCROLL_BOTTOM",
        Action::"BROWSER_ZOOM_IN",
        Action::"BROWSER_ZOOM_OUT",
        Action::"BROWSER_ZOOM_RESET",
        Action::"BROWSER_GO_BACK",
        Action::"BROWSER_GO_FORWARD",
        Action::"BROWSER_FULLSCREEN",
        Action::"BROWSER_OPEN_HISTORY",
        Action::"BROWSER_OPEN_DOWNLOADS",
        Action::"BROWSER_FIND_ON_PAGE"
    ],
    resource == Resource::"Browser"
);

// Permit screen inspection, OCR, and safe UI clicks
permit(
    principal == User::"VoiceUser",
    action in [
        Action::"READ_SCREEN",
        Action::"WHAT_IS_OPEN",
        Action::"CLICK_ELEMENT",
        Action::"CLICK_AT_MOUSE",
        Action::"SCREENSHOT"
    ],
    resource == Resource::"Screen"
);

// Permit volume, audio and window layout management
permit(
    principal == User::"VoiceUser",
    action in [
        Action::"VOLUME_UP",
        Action::"VOLUME_DOWN",
        Action::"VOLUME_MUTE",
        Action::"WINDOW_MINIMIZE",
        Action::"WINDOW_MAXIMIZE",
        Action::"WINDOW_SNAP_LEFT",
        Action::"WINDOW_SNAP_RIGHT",
        Action::"SHOW_DESKTOP",
        Action::"WINDOW_SWITCH",
        Action::"WINDOW_TASK_VIEW",
        Action::"DESKTOP_SWITCH",
        Action::"DESKTOP_NEW"
    ],
    resource == Resource::"Desktop"
);

// Permit safe form navigation and typing
permit(
    principal == User::"VoiceUser",
    action in [
        Action::"FORM_NEXT_FIELD",
        Action::"FORM_PREV_FIELD",
        Action::"FORM_FILL_FIELD",
        Action::"FORM_TOGGLE_CHECKBOX",
        Action::"FORM_SUBMIT",
        Action::"SELECT_ALL",
        Action::"CLEAR_FIELD",
        Action::"COPY_TEXT",
        Action::"PASTE_TEXT",
        Action::"UNDO_ACTION",
        Action::"TYPE_TEXT",
        Action::"TYPE_AND_SEND",
        Action::"SEND_MESSAGE",
        Action::"WHATSAPP_MESSAGE"
    ],
    resource == Resource::"Input"
);

// Permit launching approved applications and listing installed apps
permit(
    principal == User::"VoiceUser",
    action in [
        Action::"OPEN_APP",
        Action::"LIST_INSTALLED_APPS"
    ],
    resource == Resource::"Applications"
);

// Permit safe file creation and folder document listing inside approved user directories (Desktop/Documents)
permit(
    principal == User::"VoiceUser",
    action in [
        Action::"CREATE_FILE",
        Action::"LIST_FILES"
    ],
    resource == Resource::"FileSystem"
) when {
    context.is_safe_path == true
};

// Permit session exit and window close
permit(
    principal == User::"VoiceUser",
    action in [
        Action::"EXIT_ASSISTANT", 
        Action::"LOCK_SCREEN", 
        Action::"WINDOW_CLOSE", 
        Action::"BROWSER_CLOSE_TAB", 
        Action::"DESKTOP_CLOSE"
    ],
    resource == Resource::"Session"
);

// ------------------------------------------------------------------------------
// STRICT FORBID RULES: HIGHEST PRECEDENCE IN CEDAR
// ------------------------------------------------------------------------------
// Forbid dangerous file deletions or disk formatting unless confirmed
forbid(
    principal,
    action in [Action::"DELETE_FILE", Action::"FORMAT_DISK", Action::"EXEC_SHELL"],
    resource
) unless {
    context.confirmed == true
};

// Forbid file creation outside approved directories
forbid(
    principal,
    action == Action::"CREATE_FILE",
    resource == Resource::"FileSystem"
) when {
    context.is_safe_path == false
};
