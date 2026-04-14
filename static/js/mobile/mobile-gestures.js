document.addEventListener('DOMContentLoaded', function() {
    // 初始化手势操作
    initGestures();
});

function initGestures() {
    // 滑动切换页面
    initSwipeNavigation();
    
    // 下拉刷新
    initPullToRefresh();
    
    // 长按操作
    initLongPress();
    
    // 双击操作
    initDoubleTap();
}

// 滑动切换页面
function initSwipeNavigation() {
    let swipeTouchStartX = 0;
    let swipeTouchStartY = 0;
    let swipeTouchEndX = 0;
    let swipeTouchEndY = 0;
    
    document.addEventListener('touchstart', function(e) {
        swipeTouchStartX = e.changedTouches[0].screenX;
        swipeTouchStartY = e.changedTouches[0].screenY;
    }, { passive: true });
    
    document.addEventListener('touchend', function(e) {
        swipeTouchEndX = e.changedTouches[0].screenX;
        swipeTouchEndY = e.changedTouches[0].screenY;
        
        handleSwipeNavigation(swipeTouchStartX, swipeTouchStartY, swipeTouchEndX, swipeTouchEndY);
    }, { passive: true });
}

function handleSwipeNavigation(startX, startY, endX, endY) {
    const threshold = 50;
    const verticalThreshold = 100;
    
    // 计算水平和垂直滑动距离
    const deltaX = endX - startX;
    const deltaY = endY - startY;
    
    // 确保是水平滑动（垂直滑动距离小于阈值）
    if (Math.abs(deltaY) < verticalThreshold) {
        // 向右滑动
        if (deltaX > threshold) {
            handleSwipeRight();
        }
        // 向左滑动
        else if (deltaX < -threshold) {
            handleSwipeLeft();
        }
    }
}

function handleSwipeRight() {
    // 向右滑动逻辑
    // 例如：返回上一页
    const backButton = document.querySelector('.btn-back, .btn-outline-secondary[onclick*="history.back"]');
    if (backButton) {
        backButton.click();
    } else {
        // 如果没有返回按钮，使用浏览器的历史回退
        window.history.back();
    }
}

function handleSwipeLeft() {
    // 向左滑动逻辑
    // 例如：前进到下一页
    // 这里可以根据具体页面添加前进逻辑
}

// 下拉刷新
function initPullToRefresh() {
    let startY = 0;
    let currentY = 0;
    let pullDistance = 0;
    const threshold = 80;
    let isPulling = false;
    let isRefreshing = false;
    
    // 创建刷新指示器
    const refreshIndicator = document.createElement('div');
    refreshIndicator.className = 'pull-to-refresh-indicator';
    refreshIndicator.innerHTML = '<div class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></div><span>下拉刷新</span>';
    refreshIndicator.style.cssText = `
        position: fixed;
        top: -60px;
        left: 0;
        right: 0;
        height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #f8f9fa;
        z-index: 1050;
        transition: top 0.3s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    `;
    document.body.appendChild(refreshIndicator);
    
    document.addEventListener('touchstart', function(e) {
        if (window.scrollY === 0 && !isRefreshing) {
            startY = e.changedTouches[0].screenY;
            isPulling = true;
        }
    }, { passive: true });
    
    document.addEventListener('touchmove', function(e) {
        // 检查是否点击在下拉框或输入元素上
        const target = e.target;
        if (target.tagName === 'SELECT' || target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || 
            target.closest('select') || target.closest('input') || target.closest('textarea')) {
            return; // 不处理下拉框和输入元素的触摸事件
        }
        
        if (isPulling && !isRefreshing) {
            currentY = e.changedTouches[0].screenY;
            pullDistance = currentY - startY;
            
            if (pullDistance > 0) {
                // 只有当页面已经滚动到顶部时才阻止默认行为
                if (window.scrollY === 0) {
                    e.preventDefault();
                    refreshIndicator.style.top = `${Math.min(pullDistance * 0.5, threshold)}px`;
                    
                    if (pullDistance > threshold) {
                        refreshIndicator.innerHTML = '<div class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></div><span>释放刷新</span>';
                    } else {
                        refreshIndicator.innerHTML = '<div class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></div><span>下拉刷新</span>';
                    }
                }
            }
        }
    }, { passive: false });
    
    document.addEventListener('touchend', function() {
        if (isPulling && !isRefreshing) {
            if (pullDistance > threshold) {
                // 触发刷新
                isRefreshing = true;
                refreshIndicator.innerHTML = '<div class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></div><span>刷新中...</span>';
                refreshIndicator.style.top = '0px';
                
                // 模拟刷新操作
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                // 取消刷新
                refreshIndicator.style.top = '-60px';
            }
            
            isPulling = false;
            pullDistance = 0;
        }
    }, { passive: true });
}

// 长按操作
function initLongPress() {
    let pressTimer = null;
    const longPressThreshold = 500;
    
    document.addEventListener('touchstart', function(e) {
        const target = e.target;
        pressTimer = setTimeout(() => {
            handleLongPress(target);
        }, longPressThreshold);
    }, { passive: true });
    
    document.addEventListener('touchend', function() {
        if (pressTimer) {
            clearTimeout(pressTimer);
            pressTimer = null;
        }
    }, { passive: true });
    
    document.addEventListener('touchmove', function() {
        if (pressTimer) {
            clearTimeout(pressTimer);
            pressTimer = null;
        }
    }, { passive: true });
}

function handleLongPress(target) {
    // 长按逻辑
    // 例如：显示操作菜单
    if (target.tagName === 'TR' || target.closest('tr')) {
        const row = target.closest('tr');
        if (row) {
            // 触发行的上下文菜单
            const event = new MouseEvent('contextmenu', {
                bubbles: true,
                cancelable: true,
                view: window
            });
            row.dispatchEvent(event);
        }
    }
}

// 双击操作
function initDoubleTap() {
    let lastTap = 0;
    const doubleTapThreshold = 300;
    
    document.addEventListener('touchstart', function(e) {
        const currentTime = new Date().getTime();
        const tapLength = currentTime - lastTap;
        
        if (tapLength < doubleTapThreshold && tapLength > 0) {
            handleDoubleTap(e.target);
        }
        
        lastTap = currentTime;
    }, { passive: true });
}

function handleDoubleTap(target) {
    // 双击逻辑
    // 例如：快速编辑或放大
    if (target.tagName === 'TD' || target.closest('td')) {
        const cell = target.closest('td');
        if (cell) {
            // 查找对应的编辑按钮
            const editButton = cell.closest('tr').querySelector('.btn-edit-material, .btn-edit, .btn-outline-primary');
            if (editButton) {
                editButton.click();
            }
        }
    }
}

// 滑动删除（适用于列表项）
function initSwipeToDelete() {
    const listItems = document.querySelectorAll('tr, .list-group-item');
    listItems.forEach(item => {
        let touchStartX = 0;
        let touchEndX = 0;
        
        item.addEventListener('touchstart', function(e) {
            touchStartX = e.changedTouches[0].screenX;
        }, { passive: true });
        
        item.addEventListener('touchend', function(e) {
            touchEndX = e.changedTouches[0].screenX;
            const deltaX = touchEndX - touchStartX;
            
            // 向左滑动超过阈值
            if (deltaX < -80) {
                // 显示删除按钮
                const deleteButton = item.querySelector('.btn-delete, .btn-outline-danger');
                if (deleteButton) {
                    deleteButton.style.opacity = '1';
                    deleteButton.style.transform = 'translateX(0)';
                }
            }
            // 向右滑动超过阈值
            else if (deltaX > 80) {
                // 隐藏删除按钮
                const deleteButton = item.querySelector('.btn-delete, .btn-outline-danger');
                if (deleteButton) {
                    deleteButton.style.opacity = '0';
                    deleteButton.style.transform = 'translateX(100%)';
                }
            }
        }, { passive: true });
    });
}

// 初始化滑动删除
window.addEventListener('load', function() {
    initSwipeToDelete();
});