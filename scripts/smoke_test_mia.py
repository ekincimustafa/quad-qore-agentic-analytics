from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)

from app.connectors.mia_client import MiaConfigurationError, ask_mia


TEST_PROMPT = 'Yalnızca "MIA bağlantısı başarılı" yaz.'


def main() -> None:
    print("MIA bağlantısı test ediliyor...")

    try:
        answer = ask_mia(TEST_PROMPT)

    except MiaConfigurationError as error:
        print(f"Yapılandırma hatası: {error}")
        raise SystemExit(1)

    except AuthenticationError:
        print("Kimlik doğrulama başarısız. MIA API anahtarını kontrol edin.")
        raise SystemExit(1)

    except PermissionDeniedError:
        print("Bu API anahtarının seçilen modele erişim izni bulunmuyor.")
        raise SystemExit(1)

    except RateLimitError:
        print("MIA kullanım sınırına ulaşıldı. Bir süre sonra tekrar deneyin.")
        raise SystemExit(1)

    except APIConnectionError:
        print("MIA sunucusuna bağlanılamadı. İnternet bağlantısını kontrol edin.")
        raise SystemExit(1)

    except APIStatusError as error:
        print(f"MIA API isteği HTTP {error.status_code} hatasıyla sonuçlandı.")
        raise SystemExit(1)

    print("Bağlantı başarılı.")
    print(f"MIA yanıtı: {answer}")


if __name__ == "__main__":
    main()