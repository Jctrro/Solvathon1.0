document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    if (!loginForm) return;

    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const errorMsg = document.getElementById('error-msg');
    const errorText = document.getElementById('error-text');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = document.getElementById('btn-text');
    const btnIcon = document.getElementById('btn-icon');

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        errorMsg.classList.add('hidden');
        btnText.innerText = 'Authenticating...';
        btnIcon.classList.add('hidden');
        submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
        submitBtn.disabled = true;

        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: emailInput.value,
                    password: passwordInput.value
                })
            });

            const data = await res.json();
            console.log("Login Response Data:", data);

            if (!res.ok) {
                console.error("Login failed:", data.detail);
                throw new Error(data.detail || 'Login failed');
            }

            const role = data.data?.user?.role;
            console.log("Detected Role:", role);

            if (role) {
                console.log("Login successful, redirecting...");
                alert("Login Successful! Redirecting to " + role + " portal...");
            }

            if (role === 'STUDENT') {
                window.location.href = '/student.html';
            } else if (role === 'FACULTY') {
                window.location.href = '/faculty.html';
            } else if (role === 'ADMIN') {
                window.location.href = '/admin.html';
            } else {
                throw new Error("Invalid role detected");
            }
        } catch (err) {
            errorText.innerText = err.message;
            errorMsg.classList.remove('hidden');
        } finally {
            btnText.innerText = 'Enter Portal';
            btnIcon.classList.remove('hidden');
            submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            submitBtn.disabled = false;
        }
    });
});

async function handleLogout() {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
        window.location.href = '/';
    } catch (err) {
        console.error(err);
        window.location.href = '/';
    }
}
