import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("application bootstrap", () => {
  it("exports the root application component", () => {
    expect(App).toBeTypeOf("function");
  });
});
