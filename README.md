# Finanças Pessoais

Aplicação simples de gestão financeira feita com Streamlit e Firebase
Firestore. Os lançamentos são salvos na coleção `transactions` do banco
Firestore `(default)`.

## Configuração

1. No Firebase Console do projeto `despesas`, habilite o Cloud Firestore e
   crie o banco de dados padrão (`(default)`), caso ainda não exista.
2. Gere uma chave privada de uma conta de serviço em **Configurações do
   projeto > Contas de serviço**. Mantenha essa chave privada e não a envie
   para o Git ou para o navegador.
3. Copie `.streamlit/secrets.toml.example` para
   `.streamlit/secrets.toml` e preencha os campos com os valores do arquivo
   JSON da conta de serviço. Confirme que `project_id` é o ID real do projeto
   Firebase (o nome exibido no console pode ser diferente).
4. Instale as dependências e inicie o aplicativo:

   ```powershell
   python -m pip install -r requirements.txt
   streamlit run app.py
   ```

Também é possível configurar a autenticação com as variáveis de ambiente
`FIREBASE_SERVICE_ACCOUNT_PATH` (caminho para o JSON da conta de serviço) ou
`FIREBASE_SERVICE_ACCOUNT_JSON` (conteúdo JSON), além de
`FIREBASE_PROJECT_ID` se o projeto não estiver indicado no JSON.

O aplicativo permite cadastrar, listar, editar e excluir receitas e despesas.
O acesso ao Firestore é feito pelo SDK Admin no servidor; proteja as credenciais
da conta de serviço e restrinja o acesso ao aplicativo às pessoas autorizadas.
