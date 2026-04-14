/**
 * 移动端专用应用脚本
 * 包含移动端友好的交互逻辑和工具函数
 */

// 移动端应用对象
const mobileApp = {
    // 初始化应用
    init() {
        this.initEventListeners();
        this.initFormValidation();
        this.initTouchGestures();
        this.initLoadingState();
    },

    // 初始化事件监听器
    initEventListeners() {
        // 表单提交事件
        document.addEventListener('submit', (e) => {
            this.handleFormSubmit(e);
        });

        // 点击事件
        document.addEventListener('click', (e) => {
            this.handleClick(e);
        });

        // 页面滚动事件
        window.addEventListener('scroll', () => {
            this.handleScroll();
        });

        // 页面加载完成事件
        window.addEventListener('load', () => {
            this.handleLoad();
        });

        // 页面可见性变化事件
        document.addEventListener('visibilitychange', () => {
            this.handleVisibilityChange();
        });
    },

    // 处理表单提交
    handleFormSubmit(e) {
        const form = e.target;
        const submitButton = form.querySelector('button[type="submit"]');

        // 显示加载状态
        if (submitButton) {
            const originalText = submitButton.textContent;
            submitButton.textContent = '提交中...';
            submitButton.disabled = true;

            // 保存原始文本，以便表单提交后恢复
            submitButton.dataset.originalText = originalText;
        }
    },

    // 处理点击事件
    handleClick(e) {
        const target = e.target;

        // 处理返回按钮点击
        if (target.closest('.mobile-back-btn')) {
            e.preventDefault();
            window.history.back();
        }

        // 处理触摸反馈
        if (target.classList.contains('mobile-touchable')) {
            this.addTouchFeedback(target);
        }
    },

    // 处理滚动事件
    handleScroll() {
        const header = document.querySelector('.mobile-header');
        if (header) {
            if (window.scrollY > 10) {
                header.classList.add('mobile-header-scrolled');
            } else {
                header.classList.remove('mobile-header-scrolled');
            }
        }
    },

    // 处理页面加载完成
    handleLoad() {
        // 隐藏加载状态
        const loadingElement = document.querySelector('.mobile-loading');
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }

        // 初始化下拉刷新
        this.initPullToRefresh();
    },

    // 处理页面可见性变化
    handleVisibilityChange() {
        if (document.hidden) {
            // 页面不可见时的处理
        } else {
            // 页面可见时的处理
            this.refreshData();
        }
    },

    // 初始化表单验证
    initFormValidation() {
        const forms = document.querySelectorAll('.mobile-form');
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                if (!this.validateForm(form)) {
                    e.preventDefault();
                    this.showMessage('请填写所有必填字段', 'warning');
                }
            });
        });
    },

    // 验证表单
    validateForm(form) {
        const requiredFields = form.querySelectorAll('[required]');
        let isValid = true;

        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                isValid = false;
                field.classList.add('is-invalid');
            } else {
                field.classList.remove('is-invalid');
            }
        });

        return isValid;
    },

    // 初始化触摸手势
    initTouchGestures() {
        let touchStartX = 0;
        let touchStartY = 0;

        document.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        }, { passive: true });

        document.addEventListener('touchend', (e) => {
            if (!e.changedTouches[0]) return;

            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;

            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;

            // 处理左右滑动
            if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
                if (deltaX > 0) {
                    // 向右滑动
                    this.handleSwipeRight();
                } else {
                    // 向左滑动
                    this.handleSwipeLeft();
                }
            }

            // 处理上下滑动
            if (Math.abs(deltaY) > Math.abs(deltaX) && Math.abs(deltaY) > 50) {
                if (deltaY > 0) {
                    // 向下滑动
                    this.handleSwipeDown();
                } else {
                    // 向上滑动
                    this.handleSwipeUp();
                }
            }
        }, { passive: true });
    },

    // 处理向右滑动
    handleSwipeRight() {
        // 可以在这里添加向右滑动的逻辑，例如返回上一页
    },

    // 处理向左滑动
    handleSwipeLeft() {
        // 可以在这里添加向左滑动的逻辑
    },

    // 处理向下滑动
    handleSwipeDown() {
        // 可以在这里添加向下滑动的逻辑
    },

    // 处理向上滑动
    handleSwipeUp() {
        // 可以在这里添加向上滑动的逻辑
    },

    // 初始化下拉刷新
    initPullToRefresh() {
        const content = document.querySelector('.mobile-content');
        if (!content) return;

        let startY = 0;
        let isPulling = false;
        let pullDistance = 0;

        content.addEventListener('touchstart', (e) => {
            if (content.scrollTop === 0) {
                startY = e.touches[0].clientY;
                isPulling = true;
            }
        }, { passive: true });

        content.addEventListener('touchmove', (e) => {
            if (!isPulling) return;

            const currentY = e.touches[0].clientY;
            pullDistance = currentY - startY;

            if (pullDistance > 0) {
                // 阻止默认滚动行为
                e.preventDefault();
                
                // 更新下拉刷新指示器
                this.updatePullToRefreshIndicator(pullDistance);
            }
        }, { passive: false });

        content.addEventListener('touchend', () => {
            if (!isPulling) return;

            if (pullDistance > 80) {
                // 触发刷新
                this.triggerRefresh();
            }

            // 重置状态
            isPulling = false;
            pullDistance = 0;
            this.resetPullToRefreshIndicator();
        }, { passive: true });
    },

    // 更新下拉刷新指示器
    updatePullToRefreshIndicator(distance) {
        let indicator = document.querySelector('.pull-to-refresh-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.className = 'pull-to-refresh-indicator';
            indicator.style.cssText = `
                position: absolute;
                top: -50px;
                left: 0;
                right: 0;
                height: 50px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                color: #666;
                transition: transform 0.2s;
            `;
            document.querySelector('.mobile-content').prepend(indicator);
        }

        indicator.style.transform = `translateY(${Math.min(distance, 100)}px)`;
        indicator.textContent = distance > 80 ? '释放刷新' : '下拉刷新';
    },

    // 重置下拉刷新指示器
    resetPullToRefreshIndicator() {
        const indicator = document.querySelector('.pull-to-refresh-indicator');
        if (indicator) {
            indicator.style.transform = 'translateY(-50px)';
        }
    },

    // 触发刷新
    triggerRefresh() {
        const indicator = document.querySelector('.pull-to-refresh-indicator');
        if (indicator) {
            indicator.textContent = '刷新中...';
        }

        // 模拟刷新操作
        setTimeout(() => {
            this.refreshData();
            if (indicator) {
                indicator.textContent = '刷新完成';
                setTimeout(() => {
                    this.resetPullToRefreshIndicator();
                }, 1000);
            }
        }, 1500);
    },

    // 刷新数据
    refreshData() {
        // 可以在这里添加数据刷新的逻辑
        console.log('刷新数据');
    },

    // 初始化加载状态
    initLoadingState() {
        // 创建加载覆盖层
        const loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'mobileLoadingOverlay';
        loadingOverlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(255, 255, 255, 0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            display: none;
        `;

        const spinner = document.createElement('div');
        spinner.className = 'mobile-loading-spinner';
        loadingOverlay.appendChild(spinner);

        document.body.appendChild(loadingOverlay);
    },

    // 显示加载状态
    showLoading() {
        const loadingOverlay = document.getElementById('mobileLoadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'flex';
        }
    },

    // 隐藏加载状态
    hideLoading() {
        const loadingOverlay = document.getElementById('mobileLoadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
    },

    // 显示消息提示
    showMessage(message, type = 'info') {
        // 创建消息元素
        const messageElement = document.createElement('div');
        messageElement.className = `mobile-message mobile-message-${type}`;
        messageElement.style.cssText = `
            position: fixed;
            top: 60px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 20px;
            border-radius: 8px;
            color: white;
            font-size: 14px;
            z-index: 9999;
            animation: slideDown 0.3s ease-out;
        `;

        // 根据类型设置背景颜色
        switch (type) {
            case 'success':
                messageElement.style.backgroundColor = '#28a745';
                break;
            case 'error':
                messageElement.style.backgroundColor = '#dc3545';
                break;
            case 'warning':
                messageElement.style.backgroundColor = '#ffc107';
                messageElement.style.color = '#333';
                break;
            default:
                messageElement.style.backgroundColor = '#007bff';
        }

        messageElement.textContent = message;
        document.body.appendChild(messageElement);

        // 添加动画样式
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideDown {
                from {
                    transform: translate(-50%, -20px);
                    opacity: 0;
                }
                to {
                    transform: translate(-50%, 0);
                    opacity: 1;
                }
            }
        `;
        document.head.appendChild(style);

        // 3秒后移除消息
        setTimeout(() => {
            messageElement.style.animation = 'slideDown 0.3s ease-out reverse';
            setTimeout(() => {
                if (messageElement.parentNode) {
                    messageElement.parentNode.removeChild(messageElement);
                }
                if (style.parentNode) {
                    style.parentNode.removeChild(style);
                }
            }, 300);
        }, 3000);
    },

    // 添加触摸反馈
    addTouchFeedback(element) {
        element.style.transition = 'opacity 0.1s';
        element.style.opacity = '0.7';
        setTimeout(() => {
            element.style.opacity = '1';
        }, 100);
    },

    // 平滑滚动到指定元素
    scrollToElement(element, offset = 0) {
        const elementTop = element.getBoundingClientRect().top + window.pageYOffset;
        const scrollTo = elementTop - offset;

        window.scrollTo({
            top: scrollTo,
            behavior: 'smooth'
        });
    },

    // 获取URL参数
    getUrlParam(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    },

    // 设置URL参数
    setUrlParam(name, value) {
        const urlParams = new URLSearchParams(window.location.search);
        urlParams.set(name, value);
        window.history.replaceState({}, '', `${window.location.pathname}?${urlParams.toString()}`);
    },

    // 移除URL参数
    removeUrlParam(name) {
        const urlParams = new URLSearchParams(window.location.search);
        urlParams.delete(name);
        window.history.replaceState({}, '', `${window.location.pathname}?${urlParams.toString()}`);
    },

    // 检查是否为移动设备
    isMobile() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    },

    // 检查是否为iOS设备
    isIOS() {
        return /iPhone|iPad|iPod/i.test(navigator.userAgent);
    },

    // 检查是否为Android设备
    isAndroid() {
        return /Android/i.test(navigator.userAgent);
    },

    // 获取设备屏幕尺寸
    getScreenSize() {
        return {
            width: window.screen.width,
            height: window.screen.height
        };
    },

    // 获取视口尺寸
    getViewportSize() {
        return {
            width: window.innerWidth,
            height: window.innerHeight
        };
    }
};

// 初始化应用
if (typeof window !== 'undefined') {
    window.mobileApp = mobileApp;
    window.addEventListener('DOMContentLoaded', () => {
        mobileApp.init();
    });
}
