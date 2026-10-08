import { Suspense } from "react";

import { PeoplePage } from "@/components/workspace/people-page";

export default function CompaniesPeopleRoute() {
  return (
    <Suspense>
      <PeoplePage />
    </Suspense>
  );
}
