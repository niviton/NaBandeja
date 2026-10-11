"""Script Selenium simples para validar o fluxo de Garcom pela interface.

Requisitos:
- Servidor ja iniciado em http://127.0.0.1:8000
- Usuario garcom existente: niviton / 1234

Executar:
python tests/selenium_user_simulation.py
"""

from __future__ import annotations

import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "niviton"
PASSWORD = "1234"
PAUSE_SECONDS = 1.5
TIMEOUT = 20


def pause() -> None:
    time.sleep(PAUSE_SECONDS)


def log(message: str) -> None:
    print(f"[selenium] {message}")


def open_wait(driver, wait):
    log("Abrindo login")
    driver.get(f"{BASE_URL}/")
    wait.until(EC.presence_of_element_located((By.NAME, "username")))
    pause()


def login(driver, wait):
    log("Fazendo login com usuario garcom")
    driver.find_element(By.NAME, "username").clear()
    driver.find_element(By.NAME, "username").send_keys(USERNAME)
    pause()

    driver.find_element(By.NAME, "password").clear()
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    pause()

    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    wait.until(lambda d: "/garcom/" in d.current_url)
    pause()


def open_waiter(driver, wait):
    log("Abrindo tela do garcom")
    driver.get(f"{BASE_URL}/garcom/")
    wait.until(EC.presence_of_element_located((By.ID, "orderForm")))
    pause()


def fill_dine_in_header(driver, order_number):
    log(f"Preenchendo pedido de mesa #{order_number}")
    driver.find_element(By.ID, "orderTypeDineIn").click()
    pause()

    mesa = driver.find_element(By.ID, "mesaInput")
    cliente = driver.find_element(By.ID, "clienteInput")
    obs = driver.find_element(By.ID, "observacoesInput")

    mesa.clear()
    mesa.send_keys(str(10 + order_number))
    pause()

    cliente.clear()
    cliente.send_keys(f"Cliente Selenium Mesa {order_number}")
    pause()

    obs.clear()
    obs.send_keys(f"Pedido de mesa automatizado #{order_number}")
    pause()


def add_product(driver, wait):
    log("Adicionando item no carrinho")
    buttons = wait.until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "button[data-cart-action='add'][data-product-id]")
        )
    )

    for btn in buttons:
        classes = btn.get_attribute("class") or ""
        if "pointer-events-none" in classes:
            continue
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        pause()
        btn.click()
        pause()
        return

    raise RuntimeError("Nenhum botao de adicionar produto disponivel.")


def increase_decrease_item(driver, wait):
    log("Testando + e - no carrinho")
    plus_btn = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#cartItemsContainer button[data-cart-action='add']"))
    )
    plus_btn.click()
    pause()

    minus_btn = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#cartItemsContainer button[data-cart-action='remove']"))
    )
    minus_btn.click()
    pause()


def clear_cart(driver, wait):
    log("Testando limpar carrinho")
    clear_btn = wait.until(EC.element_to_be_clickable((By.ID, "clearCartBtn")))
    clear_btn.click()
    pause()


def fill_delivery_header(driver, order_number):
    log(f"Preenchendo pedido delivery #{order_number}")
    driver.find_element(By.ID, "orderTypeDelivery").click()
    pause()

    cliente = driver.find_element(By.ID, "clienteInput")
    address = driver.find_element(By.ID, "addressInput")
    obs = driver.find_element(By.ID, "observacoesInput")

    cliente.clear()
    cliente.send_keys(f"Cliente Selenium Delivery {order_number}")
    pause()

    address.clear()
    address.send_keys(f"Rua Teste, {100 + order_number} - Centro")
    pause()

    obs.clear()
    obs.send_keys(f"Pedido delivery automatizado #{order_number}")
    pause()


def submit_order(driver, wait):
    log("Enviando pedido")
    submit_btn = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'][form='orderForm']"))
    )
    submit_btn.click()

    # Espera voltar para tela com carrinho vazio ou mensagem de sucesso
    wait.until(lambda d: "Carrinho vazio" in d.page_source or "enviado para a cozinha" in d.page_source)
    pause()


def logout(driver, wait):
    log("Fazendo logout")
    driver.find_element(By.CSS_SELECTOR, "a[href='/logout/']").click()
    wait.until(EC.presence_of_element_located((By.NAME, "username")))
    pause()


def main() -> int:
    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, TIMEOUT)

    try:
        driver.set_window_size(1440, 900)
        log("Iniciando fluxo: 1 login + 10 pedidos")

        open_wait(driver, wait)
        login(driver, wait)
        open_waiter(driver, wait)

        success_count = 0
        for order_number in range(1, 11):
            log(f"--- PEDIDO {order_number}/10 ---")
            try:
                if order_number % 2 == 1:
                    fill_dine_in_header(driver, order_number)
                else:
                    fill_delivery_header(driver, order_number)

                add_product(driver, wait)
                increase_decrease_item(driver, wait)
                submit_order(driver, wait)
                success_count += 1
                log(f"PEDIDO {order_number} enviado com sucesso")
                pause()
            except TimeoutException as exc:
                log(f"ERRO de timeout no pedido {order_number}: {exc}")
                driver.get(f"{BASE_URL}/garcom/")
                wait.until(EC.presence_of_element_located((By.ID, "orderForm")))
                pause()
            except Exception as exc:
                log(f"ERRO no pedido {order_number}: {exc}")
                driver.get(f"{BASE_URL}/garcom/")
                wait.until(EC.presence_of_element_located((By.ID, "orderForm")))
                pause()

        log(f"Resumo: {success_count}/10 pedidos enviados com sucesso")
        logout(driver, wait)
        return 0 if success_count == 10 else 1

    except Exception as exc:
        log(f"ERRO fatal: {exc}")
        return 1
    finally:
        driver.quit()


if __name__ == "__main__":
    raise SystemExit(main())
