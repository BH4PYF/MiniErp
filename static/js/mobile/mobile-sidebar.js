document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const mobileMenuToggle = document.getElementById('mobileMenuToggle');
    const overlay = document.getElementById('sidebarOverlay');

    if (!sidebar || !mobileMenuToggle || !overlay) {
        return;
    }

    function isMobile() {
        return window.innerWidth < 768;
    }

    function openSidebar() {
        sidebar.classList.add('show');
        overlay.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        sidebar.classList.remove('show');
        overlay.classList.remove('show');
        document.body.style.overflow = '';
    }

    // 确保页面加载时如果遮罩层显示，自动关闭
    if (overlay.classList.contains('show')) {
        closeSidebar();
    }

    function syncToggleVisibility() {
        mobileMenuToggle.style.display = isMobile() ? 'block' : 'none';
        if (!isMobile()) {
            closeSidebar();
        }
    }

    syncToggleVisibility();

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
        });
    }

    mobileMenuToggle.addEventListener('click', openSidebar);
    overlay.addEventListener('click', closeSidebar);
    window.addEventListener('resize', syncToggleVisibility);

    // 侧边栏手势变量
    let sidebarTouchStartX = 0;
    let sidebarTouchEndX = 0;

    sidebar.addEventListener('touchstart', function(e) {
        sidebarTouchStartX = e.changedTouches[0].screenX;
    }, { passive: true });

    sidebar.addEventListener('touchend', function(e) {
        sidebarTouchEndX = e.changedTouches[0].screenX;
        if (sidebarTouchStartX - sidebarTouchEndX > 50) {
            closeSidebar();
        }
    }, { passive: true });

    // 添加从左侧滑动打开侧边栏的手势
    document.addEventListener('touchstart', function(e) {
        if (isMobile() && e.changedTouches[0].screenX < 50) {
            sidebarTouchStartX = e.changedTouches[0].screenX;
        }
    }, { passive: true });

    document.addEventListener('touchend', function(e) {
        if (isMobile() && sidebarTouchStartX < 50) {
            sidebarTouchEndX = e.changedTouches[0].screenX;
            if (sidebarTouchEndX - sidebarTouchStartX > 50) {
                openSidebar();
            }
        }
    }, { passive: true });
});

