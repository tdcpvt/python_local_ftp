(function() {
    // Structural wrapper ensuring isolated execution variables
    function initStartButtonEngine() {
        const startBtn = document.getElementById('xpStartBtnNative');
        const startMenu = document.getElementById('xpStartMenuPanel');
        const settingsWin = document.getElementById('settingsWindow');

        if (!startBtn || !startMenu) {
            console.log("[System Warning] Start menu DOM bindings missing. Retrying runtime configuration loop...");
            return;
        }

        // The Definitive Visibility Switcher Logic Rule
        function forceToggleMenuPanel(e) {
            if (e) {
                e.stopPropagation();
                e.preventDefault();
            }
            
            if (startMenu.style.display === 'block') {
                startMenu.style.display = 'none';
                startBtn.style.boxShadow = 'inset -2px 0 4px rgba(0,0,0,0.3)';
            } else {
                startMenu.style.display = 'block';
                startBtn.style.boxShadow = 'inset 2px 2px 4px rgba(0,0,0,0.6)';
            }
        }

        // Attach listeners using native touch events to bypass Desktop Mode coordinate emulation drops
        startBtn.addEventListener('touchend', forceToggleMenuPanel, { passive: false });
        startBtn.addEventListener('click', forceToggleMenuPanel);

        // Map settings password window trigger option
        const changePassOpt = document.getElementById('menuOptChangePass');
        if (changePassOpt && settingsWin) {
            changePassOpt.addEventListener('click', (e) => {
                e.preventDefault();
                settingsWin.style.display = 'flex';
                startMenu.style.display = 'none';
                startBtn.style.boxShadow = 'inset -2px 0 4px rgba(0,0,0,0.3)';
            });
        }

        // Close menu if user clicks anywhere else on the blue screen wallpaper canvas
        document.addEventListener('click', (e) => {
            if (!startMenu.contains(e.target) && !startBtn.contains(e.target)) {
                startMenu.style.display = 'none';
                startBtn.style.boxShadow = 'inset -2px 0 4px rgba(0,0,0,0.3)';
            }
        });
        
        document.addEventListener('touchend', (e) => {
            if (!startMenu.contains(e.target) && !startBtn.contains(e.target)) {
                startMenu.style.display = 'none';
                startBtn.style.boxShadow = 'inset -2px 0 4px rgba(0,0,0,0.3)';
            }
        });
    }

    // Execute verification hook safely across DOM initialization state shifts
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initStartButtonEngine);
    } else {
        initStartButtonEngine();
    }
})();
