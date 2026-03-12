/**
 * ColabPlatform - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize components
    initializeTooltips();
    initializeAlerts();
    initializeConfirmDialogs();
    initializeFileUploads();
    initializeFormValidation();
    initializeSearchFilters();
    initializeDatePickers();
    initializeProgressBars();
});

/**
 * Initialize Bootstrap tooltips
 */
function initializeTooltips() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));
}

/**
 * Auto-dismiss alerts after 5 seconds
 */
function initializeAlerts() {
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });
}

/**
 * Initialize confirmation dialogs for dangerous actions
 */
function initializeConfirmDialogs() {
    document.querySelectorAll('[data-confirm]').forEach(element => {
        element.addEventListener('click', function(e) {
            const message = this.dataset.confirm || 'Are you sure you want to proceed?';
            if (!confirm(message)) {
                e.preventDefault();
                e.stopPropagation();
            }
        });
    });
}

/**
 * Initialize drag-and-drop file uploads
 */
function initializeFileUploads() {
    const dropZones = document.querySelectorAll('.file-upload-zone');
    
    dropZones.forEach(zone => {
        const input = zone.querySelector('input[type="file"]');
        const preview = zone.querySelector('.file-preview');
        
        // Click to select files
        zone.addEventListener('click', () => input.click());
        
        // Drag events
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });
        
        zone.addEventListener('dragleave', () => {
            zone.classList.remove('dragover');
        });
        
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            input.files = e.dataTransfer.files;
            updateFilePreview(preview, input.files);
        });
        
        // File selection
        input.addEventListener('change', () => {
            updateFilePreview(preview, input.files);
        });
    });
}

/**
 * Update file preview display
 */
function updateFilePreview(container, files) {
    if (!container) return;
    
    container.innerHTML = '';
    
    Array.from(files).forEach(file => {
        const item = document.createElement('div');
        item.className = 'd-flex align-items-center p-2 bg-light rounded mb-2';
        
        const icon = getFileIcon(file.type);
        const size = formatFileSize(file.size);
        
        item.innerHTML = `
            <i class="bi ${icon} me-2 text-primary"></i>
            <span class="flex-grow-1 text-truncate">${file.name}</span>
            <small class="text-muted ms-2">${size}</small>
        `;
        
        container.appendChild(item);
    });
}

/**
 * Get Bootstrap icon class for file type
 */
function getFileIcon(mimeType) {
    const icons = {
        'application/pdf': 'bi-file-pdf',
        'image/': 'bi-file-image',
        'video/': 'bi-file-play',
        'audio/': 'bi-file-music',
        'text/': 'bi-file-text',
        'application/zip': 'bi-file-zip',
        'application/json': 'bi-file-code',
    };
    
    for (const [type, icon] of Object.entries(icons)) {
        if (mimeType.startsWith(type)) return icon;
    }
    
    return 'bi-file-earmark';
}

/**
 * Format file size in human-readable format
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Initialize form validation
 */
function initializeFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
    
    // Real-time password strength indicator
    const passwordInputs = document.querySelectorAll('input[type="password"][data-strength]');
    passwordInputs.forEach(input => {
        const indicator = document.getElementById(input.dataset.strength);
        if (indicator) {
            input.addEventListener('input', () => {
                updatePasswordStrength(input.value, indicator);
            });
        }
    });
}

/**
 * Update password strength indicator
 */
function updatePasswordStrength(password, indicator) {
    let strength = 0;
    
    if (password.length >= 8) strength += 25;
    if (/[a-z]/.test(password)) strength += 25;
    if (/[A-Z]/.test(password)) strength += 25;
    if (/[0-9]/.test(password)) strength += 12.5;
    if (/[^a-zA-Z0-9]/.test(password)) strength += 12.5;
    
    const bar = indicator.querySelector('.progress-bar');
    if (bar) {
        bar.style.width = strength + '%';
        
        bar.className = 'progress-bar';
        if (strength < 50) {
            bar.classList.add('bg-danger');
        } else if (strength < 75) {
            bar.classList.add('bg-warning');
        } else {
            bar.classList.add('bg-success');
        }
    }
}

/**
 * Initialize search filters with auto-submit
 */
function initializeSearchFilters() {
    const filterForms = document.querySelectorAll('.filter-form');
    
    filterForms.forEach(form => {
        const selects = form.querySelectorAll('select');
        selects.forEach(select => {
            select.addEventListener('change', () => form.submit());
        });
    });
}

/**
 * Initialize date pickers
 */
function initializeDatePickers() {
    // Set min date to today for future date inputs
    const futureDateInputs = document.querySelectorAll('input[type="date"][data-future]');
    const today = new Date().toISOString().split('T')[0];
    
    futureDateInputs.forEach(input => {
        input.setAttribute('min', today);
    });
}

/**
 * Initialize animated progress bars
 */
function initializeProgressBars() {
    const progressBars = document.querySelectorAll('.progress-bar[data-value]');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const bar = entry.target;
                const value = bar.dataset.value || 0;
                bar.style.width = value + '%';
                observer.unobserve(bar);
            }
        });
    }, { threshold: 0.5 });
    
    progressBars.forEach(bar => {
        bar.style.width = '0%';
        observer.observe(bar);
    });
}

/**
 * AJAX form submission
 */
function submitFormAjax(form, options = {}) {
    const formData = new FormData(form);
    const url = form.action || window.location.href;
    const method = form.method || 'POST';
    
    const headers = {
        'X-Requested-With': 'XMLHttpRequest'
    };
    
    // Add CSRF token
    const csrfToken = document.querySelector('meta[name="csrf-token"]');
    if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken.content;
    }
    
    return fetch(url, {
        method: method,
        headers: headers,
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (options.onSuccess) options.onSuccess(data);
        return data;
    })
    .catch(error => {
        if (options.onError) options.onError(error);
        throw error;
    });
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                    data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast, { autohide: true, delay: 5000 });
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

/**
 * Create toast container if not exists
 */
function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1100';
    document.body.appendChild(container);
    return container;
}

/**
 * Debounce function for search inputs
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Format date in relative time
 */
function formatRelativeTime(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 7) {
        return date.toLocaleDateString();
    } else if (days > 0) {
        return days + ' day' + (days > 1 ? 's' : '') + ' ago';
    } else if (hours > 0) {
        return hours + ' hour' + (hours > 1 ? 's' : '') + ' ago';
    } else if (minutes > 0) {
        return minutes + ' minute' + (minutes > 1 ? 's' : '') + ' ago';
    } else {
        return 'Just now';
    }
}

/**
 * Copy text to clipboard
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy', 'danger');
    });
}

/**
 * Mark notification as read via AJAX
 */
function markNotificationRead(notificationId) {
    fetch(`/notifications/${notificationId}/mark-read`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const badge = document.querySelector('.navbar .badge.bg-danger');
            if (badge) {
                const count = parseInt(badge.textContent) - 1;
                if (count <= 0) {
                    badge.remove();
                } else {
                    badge.textContent = count;
                }
            }
        }
    });
}

/**
 * Export functions for global access
 */
window.ColabPlatform = {
    submitFormAjax,
    showToast,
    debounce,
    formatRelativeTime,
    copyToClipboard,
    markNotificationRead
};
