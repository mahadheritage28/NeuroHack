importScripts("https://www.gstatic.com/firebasejs/11.4.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/11.4.0/firebase-messaging-compat.js");

// Initialize Firebase in the service worker
firebase.initializeApp({
    apiKey: "AIzaSyAGweeKp0y0VZ7DeKxdKK8rhEnHhSGXRLc",
    authDomain: "auramed-994f3.firebaseapp.com",
    projectId: "auramed-994f3",
    storageBucket: "auramed-994f3.firebasestorage.app",
    messagingSenderId: "354809982629",
    appId: "1:354809982629:web:4ebfb32645b5afe795674c",
    measurementId: "G-RSXP7LNEJL"
});

// Retrieve Firebase Messaging instance
const messaging = firebase.messaging();

// Handle background messages
messaging.onBackgroundMessage((payload) => {
    console.log("Received background message: ", payload);

    const notificationTitle = payload.notification.title;
    const notificationOptions = {
        body: payload.notification.body,
        icon: payload.notification.icon, // Optional: specify an icon
    };

    // Show notification
    self.registration.showNotification(notificationTitle, notificationOptions);
});
