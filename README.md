**1. Requisitos**

Instalar dependências:



pip install -r requirements.txt



No ficheiro utils/config.py



GROQ\_API\_KEY=YOUR\_KEY (aceder [https://console.groq.com/keys](https://console.groq.com/keys) para criar a sua API\_KEY)



**2. Executar a Aplicação**

Lançar a interface Streamlit:



streamlit run app.py



**3. Como Usar**

Escrever o pedido em linguagem natural

(ex.: “Quero um T2 em Lisboa com orçamento até 400k, perto do Hospital Santa Maria”)



**4. Notas Rápidas**

Requer Python 3.10+



Chamadas ao Groq podem ocasionalmente dar rate‑limit (o sistema reenvia automaticamente)



