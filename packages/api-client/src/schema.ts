// Generated from openapi.json by tools/api-codegen. Do not edit by hand.

export type paths = {
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
};
export type webhooks = Record<string, never>;
export type components = {
    schemas: {
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
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
};
export type $defs = Record<string, never>;
export interface operations {
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
}
