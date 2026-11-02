import { FlexibleReasonForm } from './flexible-reason-form'
export function CreateGlobalReasonForm({onDone}:{onDone?:()=>void}) {
  return <FlexibleReasonForm onDone={onDone}/>
}
