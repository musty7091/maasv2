/* Django CSRF Token Okuyucu
   Bu script, tarayıcı çerezlerinden (cookie) 'csrftoken' değerini okur 
   ve AJAX isteklerinde kullanılmak üzere hazır eder.
*/

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // İstenen cookie ismini bul
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Token'ı bir değişkene ata. Artık diğer scriptlerden 'csrftoken' diyerek erişebilirsiniz.
const csrftoken = getCookie('csrftoken');

console.log("CSRF Token hazırlandı: Güvenli AJAX işlemleri yapılabilir.");