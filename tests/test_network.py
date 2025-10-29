"""Test network connectivity from inside container"""
import socket
import ssl
import certifi

def test_dns():
    """Test DNS resolution"""
    try:
        ip = socket.gethostbyname('api.anthropic.com')
        print(f"DNS Resolution: api.anthropic.com -> {ip}")
        return True
    except Exception as e:
        print(f"DNS Resolution Failed: {e}")
        return False

def test_ssl_connection():
    """Test SSL connection to Anthropic API"""
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with socket.create_connection(('api.anthropic.com', 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname='api.anthropic.com') as ssock:
                print(f"SSL Connection: {ssock.version()}")
                print(f"   Certificate: {ssock.getpeercert()['subject']}")
                return True
    except Exception as e:
        print(f"SSL Connection Failed: {e}")
        return False

def test_http_request():
    """Test actual HTTP request"""
    try:
        import httpx
        response = httpx.get('https://api.anthropic.com', timeout=10)
        print(f"HTTP Request: Status {response.status_code}")
        return True
    except Exception as e:
        print(f"HTTP Request Failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing network connectivity from container...\n")
    print(f"Certifi bundle: {certifi.where()}\n")
    
    test_dns()
    test_ssl_connection()
    test_http_request()