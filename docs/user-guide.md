# User guide

How an analyst works with library-dss, from a dataset to an approved decision. The interface is Ukrainian, so buttons and pages are named here as they appear on the screen. How each part works is in [DESIGN.md](../DESIGN.md).

## Sign in

Open the system's address in a browser and enter the analyst's e-mail and password. An administrator creates the account with `dss create-user`. The session renews itself. The sign-out button is in the account menu at the bottom of the sidebar.

## Upload a dataset

1. Open «Датасети».
2. In the «Завантажити датасет» panel choose a JSON or JSON.gz file and press «Завантажити». Two formats are accepted: the tabular one that the libsim simulator writes ([its schema](schema/dataset.schema.json)) and the nested one, by member, which gives the descriptive analytics only.
3. The import shows its progress. A file with errors is rejected with up to 20 problems at once, for example `loans.book_id: 3 rows point to unknown books`: the table, the field and how many rows are wrong. Fix the file and upload it again.

A ready dataset appears in the list with its as-of date. Everything the system shows is computed as of that date.

## Overview and analytics

Choose the dataset in the sidebar.

- «Огляд» shows the steps to a decision (data, churn model, retention plan, content portfolio) and the library's main figures. The accented button always leads to the next step.
- «Аналітика» has a switch in the toolbar for its sections: usage, content and holds, segments, search, subscriptions, cohorts and candidate titles. Every chart can be switched to a table.

## Churn model

1. Open «Відтік», tab «Модель», and press «Навчити модель».
2. When the training ends, look at the comparison of the models with the rule "14+ days without reading", the calibration, the importance of the features and the backtest over time.
3. If the quality is acceptable, press «Активувати». Retention decisions use the active model.

The «Група ризику» tab lists the members whose paid period ends within 30 days, the highest risk first, each with the reasons for their risk. A click on a member opens all their features next to the typical values.

## Retention plan

1. Open the «План» tab.
2. Under «Умови плану» set the budget, the horizon and the price of an e-mail. Optional: limits on the number of e-mails and discounts, «Обережний режим» (the least favourable bound of each effect), «Ефекти за сегментами», or «Задати ефекти вручну» to plan with your own assumptions instead of the past campaign's estimates.
3. Press «Скласти план».

The page shows the best plan's figures, the curve of gain against budget, the actions by segment, the campaign's effects with their intervals and the members in the plan. To keep the decision, press «Затвердити план» and name it: the plan appears among the reports together with the conditions it was made under.

## Content acquisition

1. Open «Закупівля» and compare the criteria in pairs on the scale from 1 to 9. The weights and the consistency ratio (CR) update at once. If the CR is above 10%, the page names the judgements to reconsider.
2. Set the licence budget and the largest number of titles of one genre.
3. Look at the ranking, how stable each title's place is when the weights change, and the portfolio.
4. Press «Затвердити портфель». The button stays disabled while the judgements are inconsistent.

## Reports

On «Звіти» press «Новий звіт», name it and choose the analytics sections. A report is a frozen copy of the data at the moment it was made. Approved plans and portfolios are marked as decisions. Every report downloads as PDF, XLSX, CSV or JSON.
