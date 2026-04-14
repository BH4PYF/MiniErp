/**
 * 移动端导航组件
 * 包含侧边栏导航和顶部导航栏的增强功能
 */

// 移动端导航对象
const mobileNavigation = {
    // 初始化导航
    init() {
        this.initSidebar();
        this.initTopNavigation();
        this.initBottomNavigation();
    },

    // 初始化侧边栏
    initSidebar() {
        const sidebarToggle = document.querySelector('.mobile-menu-toggle');
        const sidebar = document.querySelector('.mobile-sidebar');
        const sidebarOverlay = document.querySelector('.mobile-sidebar-overlay');

        if (sidebarToggle && sidebar && sidebarOverlay) {
            // 切换侧边栏显示/隐藏
            sidebarToggle.addEventListener('click', () => {
                sidebar.classList.toggle('mobile-sidebar-open');
                sidebarOverlay.classList.toggle('mobile-sidebar-overlay-visible');
                document.body.classList.toggle('mobile-body-fixed');
            });

            // 点击遮罩层关闭侧边栏
            sidebarOverlay.addEventListener('click', () => {
                sidebar.classList.remove('mobile-sidebar-open');
                sidebarOverlay.classList.remove('mobile-sidebar-overlay-visible');
                document.body.classList.remove('mobile-body-fixed');
            });

            // 点击侧边栏链接关闭侧边栏
            const sidebarLinks = sidebar.querySelectorAll('.mobile-sidebar-link');
            sidebarLinks.forEach(link => {
                link.addEventListener('click', () => {
                    sidebar.classList.remove('mobile-sidebar-open');
                    sidebarOverlay.classList.remove('mobile-sidebar-overlay-visible');
                    document.body.classList.remove('mobile-body-fixed');
                });
            });
        }
    },

    // 初始化顶部导航栏
    initTopNavigation() {
        const header = document.querySelector('.mobile-header');
        if (header) {
            // 滚动时改变顶部导航栏样式
            window.addEventListener('scroll', () => {
                if (window.scrollY > 10) {
                    header.classList.add('mobile-header-scrolled');
                } else {
                    header.classList.remove('mobile-header-scrolled');
                }
            });

            // 处理返回按钮
            const backButton = header.querySelector('.mobile-back-btn');
            if (backButton) {
                backButton.addEventListener('click', () => {
                    window.history.back();
                });
            }
        }
    },

    // 初始化底部导航栏
    initBottomNavigation() {
        const bottomNav = document.querySelector('.mobile-bottom-nav');
        if (bottomNav) {
            // 处理底部导航栏点击
            const navItems = bottomNav.querySelectorAll('.mobile-bottom-nav-item');
            navItems.forEach(item => {
                item.addEventListener('click', (e) => {
                    // 移除所有活动状态
                    navItems.forEach(navItem => {
                        navItem.classList.remove('active');
                    });
                    // 添加当前活动状态
                    item.classList.add('active');
                });
            });
        }
    },

    // 打开侧边栏
    openSidebar() {
        const sidebar = document.querySelector('.mobile-sidebar');
        const sidebarOverlay = document.querySelector('.mobile-sidebar-overlay');
        if (sidebar && sidebarOverlay) {
            sidebar.classList.add('mobile-sidebar-open');
            sidebarOverlay.classList.add('mobile-sidebar-overlay-visible');
            document.body.classList.add('mobile-body-fixed');
        }
    },

    // 关闭侧边栏
    closeSidebar() {
        const sidebar = document.querySelector('.mobile-sidebar');
        const sidebarOverlay = document.querySelector('.mobile-sidebar-overlay');
        if (sidebar && sidebarOverlay) {
            sidebar.classList.remove('mobile-sidebar-open');
            sidebarOverlay.classList.remove('mobile-sidebar-overlay-visible');
            document.body.classList.remove('mobile-body-fixed');
        }
    },

    // 切换侧边栏
    toggleSidebar() {
        const sidebar = document.querySelector('.mobile-sidebar');
        if (sidebar) {
            if (sidebar.classList.contains('mobile-sidebar-open')) {
                this.closeSidebar();
            } else {
                this.openSidebar();
            }
        }
    },

    // 滚动到顶部
    scrollToTop() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    },

    // 滚动到指定元素
    scrollToElement(element, offset = 0) {
        const elementTop = element.getBoundingClientRect().top + window.pageYOffset;
        const scrollTo = elementTop - offset;

        window.scrollTo({
            top: scrollTo,
            behavior: 'smooth'
        });
    }
};

// 导出模块
if (typeof window !== 'undefined') {
    window.mobileNavigation = mobileNavigation;
    window.addEventListener('DOMContentLoaded', () => {
        mobileNavigation.init();
    });
}
