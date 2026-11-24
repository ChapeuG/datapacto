# Espelha este repositório no AWS CodeCommit a cada push em dev, qa ou prd.
# Configure no GitHub: o secret AWS_ROLE_ARN (role com codecommit:GitPush, via OIDC) e a variável AWS_REGION.
name: espelho-codecommit

on:
  push:
    branches: [dev, qa, prd]

permissions:
  id-token: write
  contents: read

jobs:
  mirror:
    runs-on: ubuntu-latest
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}

      - name: Espelhar no CodeCommit
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          pip install git-remote-codecommit
          git clone --mirror "https://x-access-token:${GH_TOKEN}@github.com/${{ github.repository }}" espelho
          cd espelho
          git push --mirror "codecommit::${{ vars.AWS_REGION }}://__CODECOMMIT_REPO__"
