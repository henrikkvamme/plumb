import { Effect, Schema } from "effect";

export type ApiResult<A, EncodedError> =
  | { readonly ok: true; readonly value: A }
  | { readonly ok: false; readonly error: EncodedError };

export class ApiUnavailable extends Schema.TaggedError<ApiUnavailable>()("ApiUnavailable", {
  cause: Schema.Defect(),
}) {}

export const fromApi =
  <E, EncodedError>(errors: Schema.Codec<E, EncodedError>) =>
  <A>(call: () => Promise<ApiResult<A, EncodedError>>): Effect.Effect<A, E | ApiUnavailable> =>
    Effect.tryPromise({
      catch: (cause) => new ApiUnavailable({ cause }),
      try: call,
    }).pipe(
      Effect.flatMap((result) =>
        result.ok
          ? Effect.succeed(result.value)
          : Schema.decodeEffect(errors)(result.error).pipe(
              Effect.mapError((cause) => new ApiUnavailable({ cause })),
              Effect.flatMap(Effect.fail),
            ),
      ),
    );
