import axios from 'axios';

/**
 * TACTICAL API CLIENT:
 * Configured to work seamlessly with Django's Session Authentication and CSRF protection.
 */
const api = axios.create({
    baseURL: '/missionlog/api',
    timeout: 5000,
    withCredentials: true, // Crucial for sending session cookies
    headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    }
});

// CSRF HANDSHAKE:
// Automatically read the 'csrftoken' cookie and set it as a header
api.interceptors.request.use((config) => {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    
    if (cookieValue) {
        config.headers['X-CSRFToken'] = cookieValue;
    }
    return config;
});

export default api;
