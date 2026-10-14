// Generated from openapi.json by tools/api-codegen. Do not edit by hand.

export type paths = {
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Sign in with e-mail and password */
        post: operations["login"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Sign out everywhere (revokes all tokens) */
        post: operations["logout"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The signed-in analyst */
        get: operations["get_me"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Exchange a refresh token (cookie or Bearer) for new tokens */
        post: operations["refresh_tokens"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create an account */
        post: operations["register"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/datasets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Your datasets, newest first */
        get: operations["list_datasets"];
        put?: never;
        /**
         * Upload a dataset file and queue its import
         * @description Accepts the tabular format (libsim) or the nested per-user format, as `.json` or `.json.gz`. The `Location` header points to the import job.
         */
        post: operations["upload_dataset"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/datasets/{dataset_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** One dataset */
        get: operations["get_dataset"];
        put?: never;
        post?: never;
        /** Delete a dataset with all its data, analytics, jobs and reports */
        delete: operations["delete_dataset"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/datasets/{dataset_id}/analytics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Every analytics section of a dataset */
        get: operations["get_analytics"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/datasets/{dataset_id}/analytics/{section}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** One analytics section */
        get: operations["get_analytics_section"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Liveness probe */
        get: operations["get_health"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/jobs/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Current state of a job */
        get: operations["get_job"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/jobs/{job_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Follow a job as Server-Sent Events
         * @description Sends the job whenever it changes and closes the stream once it has finished. Each event's `data` is a `JobOut` object.
         */
        get: operations["stream_job_events"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/meta/enums": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Enum codes with Ukrainian labels */
        get: operations["get_enums"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Readiness probe: database reachable, migrations applied */
        get: operations["get_ready"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Your reports, newest first */
        get: operations["list_reports"];
        put?: never;
        /** Create a report from a dataset */
        post: operations["create_report"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reports/{report_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** One report with its sections */
        get: operations["get_report"];
        put?: never;
        post?: never;
        /** Delete a report */
        delete: operations["delete_report"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reports/{report_id}/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download a report as PDF, XLSX, CSV (zip of tables) or JSON */
        get: operations["export_report"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
};
export type webhooks = Record<string, never>;
export type components = {
    schemas: {
        /** AnalystOut */
        AnalystOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Email */
            email: string;
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Role */
            role: string;
        };
        /** AnalyticsOut */
        AnalyticsOut: {
            /** Dataset Id */
            dataset_id: number;
            /** Sections */
            sections: components["schemas"]["SectionOut"][];
        };
        /** Body_upload_dataset */
        Body_upload_dataset: {
            /**
             * File
             * @description Dataset JSON, optionally gzip-compressed.
             */
            file: string;
            /** Name */
            name?: string | null;
        };
        /**
         * ChartOut
         * @description A tidy table: one row per combination of dimension values.
         */
        ChartOut: {
            /**
             * Attributes
             * @description Descriptive columns that are not plotted.
             */
            attributes: components["schemas"]["DimensionOut"][];
            /** Dimensions */
            dimensions: components["schemas"]["DimensionOut"][];
            /**
             * Key
             * @description Chart code; title in enums `chart`.
             */
            key: string;
            /** Measures */
            measures: components["schemas"]["MeasureOut"][];
            /** Rows */
            rows: {
                [key: string]: string | number | null;
            }[];
            /**
             * Window Days
             * @description The value covers the last N days up to as_of; null: the whole history, or the state at the end of as_of for current counts (paying subscribers, MRR).
             */
            window_days: number | null;
        };
        /** DatasetOut */
        DatasetOut: {
            /**
             * As Of
             * @description Snapshot date: the data ends on this day.
             */
            as_of: string | null;
            /**
             * Capabilities
             * @description Modules this dataset supports.
             */
            capabilities: ("descriptive" | "retention" | "content")[];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            error: components["schemas"]["TaskError"] | null;
            /**
             * Format
             * @description File structure: `tabular` (tables of rows, as libsim writes them) or `nested` (one object per user). null until the file is parsed.
             */
            format: ("tabular" | "nested") | null;
            /** Id */
            id: number;
            /**
             * Meta
             * @description File metadata (generator, seed, ...).
             */
            meta: {
                [key: string]: unknown;
            };
            /** Name */
            name: string;
            /** Row Counts */
            row_counts: {
                [key: string]: number;
            };
            /**
             * Schema Version
             * @description Format version declared by a tabular file.
             */
            schema_version: number | null;
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "importing" | "ready" | "failed";
            /**
             * Timezone
             * @description IANA time zone of the library, e.g. `Europe/Kyiv`.
             */
            timezone: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** DatasetPage */
        DatasetPage: {
            /** Items */
            items: components["schemas"]["DatasetOut"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /**
             * Total
             * @description Number of items across all pages.
             */
            total: number;
        };
        /** DimensionOut */
        DimensionOut: {
            /**
             * Enum
             * @description Enums group with labels for the values.
             */
            enum: string | null;
            /**
             * Key
             * @description Column of the rows; label in enums `dimension`.
             */
            key: string;
            /**
             * Kind
             * @description `time` values are ISO dates (week or month start, local time).
             * @enum {string}
             */
            kind: "category" | "time" | "number";
            /**
             * Order
             * @description Display order of category values.
             */
            order: string[] | null;
        };
        /** EnumItem */
        EnumItem: {
            /** Code */
            code: string;
            /** Label */
            label: string;
        };
        /** EnumsOut */
        EnumsOut: {
            /** Enums */
            enums: {
                [key: string]: components["schemas"]["EnumItem"][];
            };
        };
        /** FieldError */
        FieldError: {
            /**
             * Loc
             * @description Path to the invalid field, e.g. ['body', 'email'].
             */
            loc: (string | number)[];
            /** Msg */
            msg: string;
            /** Type */
            type: string;
        };
        /** HealthOut */
        HealthOut: {
            /**
             * Status
             * @default ok
             * @constant
             */
            status: "ok";
            /** Version */
            version: string;
        };
        /**
         * JobOut
         * @description A long-running operation; poll it or follow `GET /jobs/{id}/events`.
         */
        JobOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Dataset Id */
            dataset_id: number | null;
            error: components["schemas"]["TaskError"] | null;
            /** Finished At */
            finished_at: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @description What the job does, e.g. `import_dataset`.
             */
            kind: string;
            /** Progress */
            progress: number;
            /** Result */
            result: {
                [key: string]: unknown;
            } | null;
            /**
             * Stage
             * @description Current step, e.g. `parse` or `load:loans`.
             */
            stage: string | null;
            /** Started At */
            started_at: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "succeeded" | "failed";
        };
        /** KpiOut */
        KpiOut: {
            /**
             * Key
             * @description Metric code; label in enums `metric`.
             */
            key: string;
            /**
             * Unit
             * @description `ratio` is a fraction 0..1 (show as a percentage).
             * @enum {string}
             */
            unit: "count" | "ratio" | "UAH" | "minutes" | "days" | "rating";
            /**
             * Value
             * @description null when this dataset cannot provide it (see notes).
             */
            value: number | null;
            /**
             * Window Days
             * @description The value covers the last N days up to as_of; null: the whole history, or the state at the end of as_of for current counts (paying subscribers, MRR).
             */
            window_days: number | null;
        };
        /** LoginIn */
        LoginIn: {
            /**
             * Email
             * Format: email
             */
            email: string;
            /**
             * Include Refresh Token
             * @description Also return the refresh token in the body (CLI/scripts). Browsers rely on the httpOnly cookie instead.
             * @default false
             */
            include_refresh_token: boolean;
            /** Password */
            password: string;
        };
        /** MeasureOut */
        MeasureOut: {
            /**
             * Key
             * @description Column of the rows; label in enums `metric`.
             */
            key: string;
            /**
             * Unit
             * @enum {string}
             */
            unit: "count" | "ratio" | "UAH" | "minutes" | "days" | "rating";
            /**
             * Window Days
             * @description Set when it differs from the chart's window.
             */
            window_days: number | null;
        };
        /** NoteOut */
        NoteOut: {
            /** Code */
            code: string;
            /** Message Uk */
            message_uk: string;
            /** Params */
            params: {
                [key: string]: unknown;
            };
        };
        /**
         * Problem
         * @description Error response (RFC 9457 Problem Details) with a stable machine-readable code.
         */
        Problem: {
            /**
             * Code
             * @description Stable error code, e.g. `dataset.not_ready`.
             */
            code: string;
            /** Detail */
            detail?: string | null;
            /** Errors */
            errors?: components["schemas"]["FieldError"][];
            /** Status */
            status: number;
            /** Title */
            title: string;
            /**
             * Type
             * @default about:blank
             */
            type: string;
        };
        /** ReadyOut */
        ReadyOut: {
            /**
             * Database
             * @default ok
             * @constant
             */
            database: "ok";
            /**
             * Migrations
             * @default ok
             * @constant
             */
            migrations: "ok";
            /**
             * Status
             * @default ready
             * @constant
             */
            status: "ready";
        };
        /** RegisterIn */
        RegisterIn: {
            /**
             * Email
             * Format: email
             */
            email: string;
            /** Name */
            name: string;
            /** Password */
            password: string;
        };
        /** ReportDetailOut */
        ReportDetailOut: {
            /**
             * As Of
             * Format: date
             */
            as_of: string;
            /**
             * Content
             * @description The sections as they were when created.
             */
            content: components["schemas"]["SectionOut"][];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Dataset Id */
            dataset_id: number;
            /** Dataset Name */
            dataset_name: string;
            /** Id */
            id: number;
            /** Sections */
            sections: ("overview" | "usage" | "content" | "segments" | "search" | "subscriptions" | "cohorts")[];
            /** Timezone */
            timezone: string;
            /** Title */
            title: string;
        };
        /** ReportIn */
        ReportIn: {
            /** Dataset Id */
            dataset_id: number;
            /**
             * Sections
             * @description Sections to include; all when omitted.
             */
            sections?: ("overview" | "usage" | "content" | "segments" | "search" | "subscriptions" | "cohorts")[] | null;
            /** Title */
            title: string;
        };
        /** ReportOut */
        ReportOut: {
            /**
             * As Of
             * Format: date
             */
            as_of: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Dataset Id */
            dataset_id: number;
            /** Dataset Name */
            dataset_name: string;
            /** Id */
            id: number;
            /** Sections */
            sections: ("overview" | "usage" | "content" | "segments" | "search" | "subscriptions" | "cohorts")[];
            /** Timezone */
            timezone: string;
            /** Title */
            title: string;
        };
        /** ReportPage */
        ReportPage: {
            /** Items */
            items: components["schemas"]["ReportOut"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /**
             * Total
             * @description Number of items across all pages.
             */
            total: number;
        };
        /** SectionOut */
        SectionOut: {
            /**
             * As Of
             * Format: date
             */
            as_of: string;
            /** Charts */
            charts: components["schemas"]["ChartOut"][];
            /**
             * Key
             * @enum {string}
             */
            key: "overview" | "usage" | "content" | "segments" | "search" | "subscriptions" | "cohorts";
            /** Kpis */
            kpis: components["schemas"]["KpiOut"][];
            /** Notes */
            notes: components["schemas"]["NoteOut"][];
            /** Timezone */
            timezone: string;
        };
        /**
         * TaskError
         * @description Why a job (and the dataset it worked on) failed.
         */
        TaskError: {
            /**
             * Code
             * @description Stable error code, e.g. `dataset.invalid`.
             */
            code: string;
            /** Detail */
            detail?: string | null;
            /**
             * Errors
             * @description Individual problems found in the file (at most 20).
             */
            errors?: string[];
        };
        /** TokenOut */
        TokenOut: {
            /** Access Token */
            access_token: string;
            /**
             * Expires In
             * @description Access token lifetime in seconds.
             */
            expires_in: number;
            /** Refresh Token */
            refresh_token?: string | null;
            /**
             * Token Type
             * @default bearer
             * @constant
             */
            token_type: "bearer";
        };
        /** UploadAccepted */
        UploadAccepted: {
            dataset: components["schemas"]["DatasetOut"];
            job: components["schemas"]["JobOut"];
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
};
export type $defs = Record<string, never>;
export interface operations {
    login: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    logout: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_me: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalystOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    refresh_tokens: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    register: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegisterIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalystOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_datasets: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DatasetPage"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    upload_dataset: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_dataset"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadAccepted"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_dataset: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dataset_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DatasetOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    delete_dataset: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dataset_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_analytics: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dataset_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_analytics_section: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dataset_id: number;
                section: "overview" | "usage" | "content" | "segments" | "search" | "subscriptions" | "cohorts";
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SectionOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_health: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_job: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    stream_job_events: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": unknown;
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_enums: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnumsOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_ready: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadyOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    list_reports: {
        parameters: {
            query?: {
                dataset_id?: number | null;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReportPage"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    create_report: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReportIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReportOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    get_report: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                report_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReportDetailOut"];
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    delete_report: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                report_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
    export_report: {
        parameters: {
            query?: {
                format?: "pdf" | "xlsx" | "csv" | "json";
            };
            header?: never;
            path: {
                report_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The report file (`Content-Disposition: attachment`). */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                    "application/pdf": unknown;
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": unknown;
                    "application/zip": unknown;
                };
            };
            /** @description Request validation failed */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
            /** @description Error (RFC 9457 Problem Details) */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Problem"];
                };
            };
        };
    };
}
