# Кресленики (конструкторські документи) — шифр ІС23.110БАК.005

> Ці чотири діаграми оформлюються **окремими аркушами формату А3** і **не
> вбудовуються** у пояснювальну записку. У тексті ПЗ на них наведено лише
> посилання за шифром. Тут зібрано вихідний код mermaid для рендерингу на
> кресленики (рамку та основний напис додає користувач вручну).

---

## ІС23.110БАК.005 Д1 — Діаграма варіантів використання

Mermaid не має нативної UML-форми use-case, тому актора зображено прямокутником
зліва, а варіанти використання — закругленими вузлами; пунктирні стрілки з
позначкою «include» — відношення включення.

```mermaid
graph LR
    user["Користувач"]

    reg(["Реєстрація / авторизація"])
    svc(["Ведення сервісів"])
    grp(["Ведення груп сервісів"])
    prov(["Ведення провайдерів"])
    plan(["Введення планових даних"])
    form(["Формування пакетів"])
    detail(["Перегляд деталей формування"])
    chart(["Перегляд графіка збіжності"])
    cmp(["Порівняння сценаріїв"])
    exp(["Експорт результатів"])

    m1(["Ймовірнісно-жадібний метод"])
    m2(["Метод мурашиних колоній"])
    m3(["Комбінований метод"])

    user --- reg
    user --- svc
    user --- grp
    user --- prov
    user --- plan
    user --- form
    user --- detail
    user --- cmp
    user --- exp

    grp -.->|"«include»"| svc
    form -.->|"«include»"| plan
    form -.->|"«include»"| m1
    form -.->|"«include»"| m2
    form -.->|"«include»"| m3
    detail -.->|"«include»"| chart
```

---

## ІС23.110БАК.005 Д2 — Діаграма класів / компонентів

Компонентний склад монорепозиторію та напрям викликів і потоків даних: клієнт
(шари FSD) → API (роутери, моделі, безпека) → обчислювальний воркер (workflows,
activities) → Rust-бібліотека `assignment_solver` (три розв'язувачі); збоку —
PostgreSQL і Redis.

```mermaid
flowchart TB
    subgraph UI["Клієнт (React, FSD)"]
        ui_pages["pages / widgets / features"]
        ui_entities["entities / shared (api-клієнт)"]
        ui_store["Zustand + react-query"]
    end

    subgraph API["API (FastAPI)"]
        routers["Роутери: auth, services,\nservice_groups, providers,\nplanning, formations"]
        security["security (JWT, bcrypt)"]
        models_db["Моделі SQLAlchemy + Alembic"]
        temporal_client["Клієнт Temporal"]
    end

    subgraph WK["Обчислювальний воркер (Temporal)"]
        wf["workflows:\nSingleAlgorithmWorkflow,\nCombinedFormationWorkflow"]
        act["activities:\nrun_*_activity,\npersist_*_activity"]
        metrics["compute_provider_metrics"]
    end

    subgraph RS["Бібліотека assignment_solver (Rust, PyO3)"]
        task["CombinedTask"]
        prob["ProbabilisticAssignmentSolver"]
        ant["AntColonyAssignmentSolver"]
        comb["CombinedSolver"]
    end

    pg[("PostgreSQL")]
    rd[("Redis")]

    ui_pages --> ui_entities --> ui_store
    ui_entities -->|"REST / JWT"| routers
    routers --> security
    routers --> models_db --> pg
    routers --> temporal_client -->|"gRPC"| wf
    wf --> act
    act --> wf
    act -->|"PyO3"| task
    task --> prob & ant & comb
    act -->|"прогрес ітерацій"| rd
    act --> metrics
    act -->|"результат, метрики"| pg
```

---

## ІС23.110БАК.005 Д3 — Діаграма розгортання

Фізичне розміщення компонентів за вузлами та протоколи з'єднання.

```mermaid
graph TB
    subgraph client_node["Вузол: браузер користувача"]
        browser["Вебзастосунок (React SPA)"]
    end

    subgraph server_node["Вузол: сервер застосунків"]
        api["Сервіс API (FastAPI)"]
        worker["Обчислювальний воркер"]
        temporal["Сервіс Temporal"]
    end

    subgraph data_node["Вузол: сховища даних"]
        pg[("PostgreSQL")]
        redis[("Redis")]
    end

    browser -->|"HTTPS / REST"| api
    api -->|"gRPC"| temporal
    worker -->|"gRPC"| temporal
    api -->|"протокол PostgreSQL"| pg
    worker -->|"протокол PostgreSQL"| pg
    worker -->|"протокол Redis"| redis
    api -->|"протокол Redis"| redis
```

---

## ІС23.110БАК.005 Д4 — Діаграма послідовності

Сценарій формування пакетів сервісів: введення даних, валідація (гілка alt:
помилка / успіх), запуск робочого процесу, стрімінг ітерацій у Redis і збереження
у PostgreSQL.

```mermaid
sequenceDiagram
    actor U as Користувач
    participant UI as Клієнт (UI)
    participant API as API (FastAPI)
    participant T as Воркер (Temporal)
    participant S as Rust-розв'язувач
    participant DB as PostgreSQL
    participant R as Redis

    U->>UI: Ввести планові дані, параметри, T
    U->>UI: Натиснути «Сформувати пакети»
    UI->>UI: Валідація вхідних даних
    alt Помилка валідації
        UI-->>U: Відобразити повідомлення про помилку
    else Успішна валідація
        UI->>API: POST /api/formations
        API->>API: Агрегація груп, побудова матриць
        API->>DB: Зберегти сценарій і знімок
        API->>T: Запустити workflow формування
        API-->>UI: 201 Created (сценарій pending)
        T->>S: Виклик розв'язувача (PyO3)
        loop Кожна ітерація
            S->>R: XADD прогрес ітерації
        end
        S-->>T: v, r, F_IT, F_prov
        T->>DB: Зберегти призначення, метрики, історію
        loop Опитування статусу
            UI->>API: GET /api/formations/{id}
            API->>DB: Прочитати стан і результат
            API-->>UI: Статус, метрики, графік
        end
        UI-->>U: Відобразити результат і графік збіжності
    end
```
