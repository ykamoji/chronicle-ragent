export const API_URL = process.env.NEXT_PUBLIC_API_URL ?
    `https://${process.env.NEXT_PUBLIC_API_URL}.onrender.com` : "http://127.0.0.1:5000"