document.addEventListener('DOMContentLoaded', function() {
    // 初始化页面加载动画
    initPageLoader();
    
    // 初始化骨架屏
    initSkeletons();
    
    // 初始化延迟加载
    initLazyLoad();
    
    // 模拟数据加载完成
    setTimeout(function() {
        hidePageLoader();
        showContent();
    }, 1000);
});

// 初始化页面加载动画
function initPageLoader() {
    // 创建页面加载条
    const pageLoader = document.createElement('div');
    pageLoader.className = 'page-loader';
    
    const progressBar = document.createElement('div');
    progressBar.className = 'page-loader-progress';
    pageLoader.appendChild(progressBar);
    
    document.body.appendChild(pageLoader);
    
    // 模拟加载进度
    let progress = 0;
    const interval = setInterval(function() {
        progress += 5;
        progressBar.style.width = `${progress}%`;
        
        if (progress >= 100) {
            clearInterval(interval);
        }
    }, 50);
}

// 隐藏页面加载动画
function hidePageLoader() {
    const pageLoader = document.querySelector('.page-loader');
    if (pageLoader) {
        pageLoader.style.opacity = '0';
        setTimeout(function() {
            pageLoader.remove();
        }, 300);
    }
}

// 初始化骨架屏
function initSkeletons() {
    // 为表格添加骨架屏
    initTableSkeletons();
    
    // 为卡片添加骨架屏
    initCardSkeletons();
    
    // 为表单添加骨架屏
    initFormSkeletons();
}

// 为表格添加骨架屏
function initTableSkeletons() {
    const tables = document.querySelectorAll('.table-responsive');
    tables.forEach(table => {
        // 检查表格是否为空
        const tbody = table.querySelector('tbody');
        if (tbody && tbody.querySelector('tr') === null) {
            // 创建骨架屏
            const skeletonContainer = document.createElement('div');
            skeletonContainer.className = 'skeleton-container p-4';
            
            // 创建多行骨架屏
            for (let i = 0; i < 5; i++) {
                const row = document.createElement('div');
                row.className = 'skeleton-table-row';
                
                // 创建多个单元格
                for (let j = 0; j < 5; j++) {
                    const cell = document.createElement('div');
                    cell.className = 'skeleton skeleton-table-cell';
                    row.appendChild(cell);
                }
                
                skeletonContainer.appendChild(row);
            }
            
            table.appendChild(skeletonContainer);
        }
    });
}

// 为卡片添加骨架屏
function initCardSkeletons() {
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        // 检查卡片是否为空
        const cardBody = card.querySelector('.card-body');
        if (cardBody && cardBody.innerHTML.trim() === '') {
            // 创建骨架屏
            const skeletonContainer = document.createElement('div');
            skeletonContainer.className = 'skeleton-container p-4';
            
            // 创建标题骨架
            const titleSkeleton = document.createElement('div');
            titleSkeleton.className = 'skeleton skeleton-text large';
            skeletonContainer.appendChild(titleSkeleton);
            
            // 创建内容骨架
            for (let i = 0; i < 3; i++) {
                const textSkeleton = document.createElement('div');
                textSkeleton.className = 'skeleton skeleton-text medium';
                skeletonContainer.appendChild(textSkeleton);
            }
            
            // 创建按钮骨架
            const buttonSkeleton = document.createElement('div');
            buttonSkeleton.className = 'skeleton skeleton-button';
            skeletonContainer.appendChild(buttonSkeleton);
            
            cardBody.appendChild(skeletonContainer);
        }
    });
}

// 为表单添加骨架屏
function initFormSkeletons() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        // 检查表单是否有输入字段
        const inputs = form.querySelectorAll('input, select, textarea');
        if (inputs.length > 0) {
            // 为每个输入字段添加骨架屏
            inputs.forEach(input => {
                // 创建骨架屏容器
                const parent = input.parentElement;
                if (parent) {
                    // 创建骨架屏
                    const skeleton = document.createElement('div');
                    skeleton.className = 'skeleton skeleton-input';
                    skeleton.style.display = 'none';
                    
                    // 存储原始输入字段
                    input.dataset.originalStyle = input.style.cssText;
                    
                    // 添加到父元素
                    parent.appendChild(skeleton);
                }
            });
        }
    });
}

// 显示内容，隐藏骨架屏
function showContent() {
    // 隐藏所有骨架屏
    const skeletons = document.querySelectorAll('.skeleton-container');
    skeletons.forEach(skeleton => {
        skeleton.style.opacity = '0';
        setTimeout(function() {
            skeleton.remove();
        }, 300);
    });
    
    // 显示所有延迟加载的元素
    const lazyElements = document.querySelectorAll('.lazy-load');
    lazyElements.forEach(element => {
        element.classList.add('loaded');
    });
}

// 初始化延迟加载
function initLazyLoad() {
    // 为所有需要延迟加载的元素添加类
    const elements = document.querySelectorAll('img, .card, .table, .form-group');
    elements.forEach(element => {
        element.classList.add('lazy-load');
    });
    
    // 监听滚动事件，触发延迟加载
    window.addEventListener('scroll', function() {
        const lazyElements = document.querySelectorAll('.lazy-load:not(.loaded)');
        lazyElements.forEach(element => {
            const rect = element.getBoundingClientRect();
            if (rect.top < window.innerHeight && rect.bottom >= 0) {
                element.classList.add('loaded');
            }
        });
    });
    
    // 初始检查
    const lazyElements = document.querySelectorAll('.lazy-load:not(.loaded)');
    lazyElements.forEach(element => {
        const rect = element.getBoundingClientRect();
        if (rect.top < window.innerHeight && rect.bottom >= 0) {
            element.classList.add('loaded');
        }
    });
}

// 显示加载覆盖层
function showLoadingOverlay() {
    // 检查是否已经存在
    if (document.querySelector('.loading-overlay')) {
        return;
    }
    
    // 创建加载覆盖层
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    
    const spinner = document.createElement('div');
    spinner.className = 'loading-spinner';
    overlay.appendChild(spinner);
    
    document.body.appendChild(overlay);
}

// 隐藏加载覆盖层
function hideLoadingOverlay() {
    const overlay = document.querySelector('.loading-overlay');
    if (overlay) {
        overlay.style.opacity = '0';
        setTimeout(function() {
            overlay.remove();
        }, 300);
    }
}

// 模拟数据加载
function simulateDataLoading(callback) {
    showLoadingOverlay();
    
    // 模拟加载时间
    setTimeout(function() {
        hideLoadingOverlay();
        if (callback) {
            callback();
        }
    }, 1500);
}

// 为AJAX请求添加加载状态
function initAjaxLoading() {
    // 监听所有AJAX请求
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        // 仅在非GET请求时显示加载状态，避免频繁的GET请求导致界面闪烁
        if (args.length > 1 && args[1].method && args[1].method !== 'GET') {
            showLoadingOverlay();
            return originalFetch.apply(this, args).finally(function() {
                hideLoadingOverlay();
            });
        } else {
            return originalFetch.apply(this, args);
        }
    };
    
    // 监听XMLHttpRequest
    const originalXHR = XMLHttpRequest;
    XMLHttpRequest = function() {
        const xhr = new originalXHR();
        xhr.addEventListener('loadstart', function() {
            // 仅在非GET请求时显示加载状态
            if (xhr.method && xhr.method !== 'GET') {
                showLoadingOverlay();
            }
        });
        xhr.addEventListener('loadend', function() {
            hideLoadingOverlay();
        });
        return xhr;
    };
    XMLHttpRequest.prototype = originalXHR.prototype;
    XMLHttpRequest.DONE = originalXHR.DONE;
    XMLHttpRequest.OPENED = originalXHR.OPENED;
    XMLHttpRequest.HEADERS_RECEIVED = originalXHR.HEADERS_RECEIVED;
    XMLHttpRequest.LOADING = originalXHR.LOADING;
    XMLHttpRequest.UNSENT = originalXHR.UNSENT;
}

// 初始化AJAX加载状态
// 暂时禁用，避免频繁的AJAX请求导致界面闪烁
// window.addEventListener('load', function() {
//     initAjaxLoading();
// });