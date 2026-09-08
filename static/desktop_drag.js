/**
 * LFT Server - Windows XP Drag & Drop Engine
 * Handles window title bar dragging and desktop icon positioning.
 */

// --- 1. WINDOW DRAGGING LOGIC ---
function makeWindowDraggable(windowElement, handleElement) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

    // Use header/title bar as drag handle if provided, otherwise the whole element
    const dragHandle = handleElement || windowElement;
    dragHandle.style.cursor = 'move';

    dragHandle.onmousedown = dragMouseDown;
    
    // Touch support for mobile/Termux desktop mode
    dragHandle.ontouchstart = dragTouchStart;

    function dragMouseDown(e) {
        e.preventDefault();
        // Bring window to front
        focusWindow(windowElement);
        
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        document.onmousemove = elementDrag;
    }

    function elementDrag(e) {
        e.preventDefault();
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;

        // Calculate new positions
        let newTop = windowElement.offsetTop - pos2;
        let newLeft = windowElement.offsetLeft - pos1;

        // Keep within viewport boundaries
        const maxLeft = window.innerWidth - windowElement.offsetWidth;
        const maxTop = window.innerHeight - windowElement.offsetHeight - 40; // 40px taskbar safety margin

        windowElement.style.top = Math.max(0, Math.min(newTop, maxTop)) + "px";
        windowElement.style.left = Math.max(0, Math.min(newLeft, maxLeft)) + "px";
    }

    function closeDragElement() {
        document.onmouseup = null;
        document.onmousemove = null;
    }

    // Touch Event Handlers
    function dragTouchStart(e) {
        focusWindow(windowElement);
        const touch = e.touches[0];
        pos3 = touch.clientX;
        pos4 = touch.clientY;
        document.ontouchend = closeTouchDrag;
        document.ontouchmove = touchDrag;
    }

    function touchDrag(e) {
        const touch = e.touches[0];
        pos1 = pos3 - touch.clientX;
        pos2 = pos4 - touch.clientY;
        pos3 = touch.clientX;
        pos4 = touch.clientY;

        let newTop = windowElement.offsetTop - pos2;
        let newLeft = windowElement.offsetLeft - pos1;

        windowElement.style.top = Math.max(0, newTop) + "px";
        windowElement.style.left = Math.max(0, newLeft) + "px";
    }

    function closeTouchDrag() {
        document.ontouchend = null;
        document.ontouchmove = null;
    }
}

// Higher z-index on click to bring active window to front
function focusWindow(element) {
    document.querySelectorAll('.xp-window').forEach(win => {
        win.style.zIndex = "100";
    });
    element.style.zIndex = "1000";
}

// --- 2. DESKTOP ICON DRAGGING LOGIC ---
function makeIconDraggable(iconElement) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

    iconElement.style.position = 'absolute';
    iconElement.style.cursor = 'pointer';

    iconElement.onmousedown = (e) => {
        e.preventDefault();
        pos3 = e.clientX;
        pos4 = e.clientY;

        document.onmouseup = () => {
            document.onmouseup = null;
            document.onmousemove = null;
        };

        document.onmousemove = (e) => {
            e.preventDefault();
            pos1 = pos3 - e.clientX;
            pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;

            iconElement.style.top = (iconElement.offsetTop - pos2) + "px";
            iconElement.style.left = (iconElement.offsetLeft - pos1) + "px";
        };
    };
}

// Automatically bind draggable triggers when DOM loads
document.addEventListener("DOMContentLoaded", () => {
    // Bind all XP Windows by header handle
    document.querySelectorAll('.xp-window').forEach(win => {
        const header = win.querySelector('.xp-window-header');
        makeWindowDraggable(win, header);
    });

    // Bind all Desktop Shortcut Icons
    document.querySelectorAll('.desktop-shortcut').forEach(icon => {
        makeIconDraggable(icon);
    });
});