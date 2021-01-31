# BigQuery Workflow

## 概要
yamlファイルにBigQuerySQLの実行順序を記述し、その順番にクエリを実行するコマンドラインツールです。

## Usage

```
Usage: bqflow [OPTIONS] FILE_PATH

Options:
  -P, --project TEXT  プロジェクトID
  -o, --output TEXT   アウトプットパス
  --entrypoint TEXT   entrypoint上書き
  --help              Show this message and exit.
```

## ワークフローの記述
ワークフローはyamlを用いて記述する。

```bash
bqflow workflow.yaml
```

のコマンドを実行すると指定した`workflow.yaml`の内容に従い、タスクが実行される。

### entrypoint
後述する`templates`のタイプが`steps`または`dag`の名前を指定する。  
指定したtemplateがワークフローを実行するときに最初に実行される。

### templates
yamlの直下に記述し、`run`,`script`,`steps`,`dag`の四種類がある。

```yaml
templates:
- name: hoge
  run/script/steps/dag: ...
```

以上のような形で記述し、複数記述できる。

#### run
実行したいクエリを直接yamlに記述するために使う。  
ただし、単体では意味をなさずこれを`steps`または`dag`で呼び出して初めて実行される。

```yaml
templates:
- name: a
  run: |
    CREATE OR REPLACE TABLE test.a AS
    SELECT 1 AS id
```

#### script
実行したいクエリを別のファイルから指定するときに使う。  
`run`の外部参照版。  
相対パスで参照する場合はコマンドを実行した場所からであることに注意。

```yaml
templates:
- name: hoge
  script: sql/hoge.sql
```

#### steps表記
後述のdagと同じで`run`または`script`で設定されたtemplateを呼び出してワークフローを記述する。

`steps:`以下にstepを記述し、複数のタスクを記述できる。  
クエリを実行する場合は以下の`templates: hoge`のように`run`または`script`で記述した、templateを指定できる。
また、`templates`には`steps`または`dag`の名前を記述できワークフローをネストして記述することもできる。
ただし、循環するように記述はできないので注意する。

```yaml
templates:
- name: main
  steps:
  - - name: step1-A
      templates: hoge
    - name: step1-B
      ...
  - - name: step2
      ...

- name: hoge
  script: sql/hoge.sql
```

以上のように記述した場合、step1-A,step1-Bは並列に実行されstep2はstep1の二つのタスクが完了されるまで実行されない。

#### DAG表記
SQLの実行順序をDAGを用いて記述する

```yaml
templates:
- name: diamond
  dag:
  - name: A
    templates: hoge
  - name: B
    dependencies: [A]
    ...
  - name: C
    dependencies: [A]
    ...
  - name: D
    dependencies: [B, C]
    ...
```

以上のように記述した場合、Aの実行後にB,Cの実行が並列で行われ、その二つが完了後にDが実行される。

### パラメータの記述
BigQuerySQLの`@`を用いたパラメータ指定をサポートしている。

```sql
CREATE OR REPLACE TABLE test.a AS
SELECT @id AS id
```

と書かれたSQLがの`@id`部分に任意の値を渡したいとする。

`run`を使ってこのクエリを記述するとき`inputs`を使って何がパラメータであるのか記述できる。

```yaml
templates:
- name: paramed
  run: |
    CREATE OR REPLACE TABLE test.a AS
    SELECT @id AS id
  inputs:
    parameters:
    - name: id
```

そして、`dag`か`steps`を用いて実際のパラメータを設定できる。

```yaml
templates:
- name: workflow
  steps:
  - - name: A
      template: paramed
      arguments:
        parameters:
        - {name: id, type: INT64, value: 1}
```

これで、paramedのtemplateのクエリのパラメータ`id`にINT64型で`1`を渡すことになる。  
ここで使える型はBigQueryに準拠している。
