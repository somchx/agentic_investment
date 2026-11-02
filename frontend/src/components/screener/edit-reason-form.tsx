import { FlexibleReasonForm } from './flexible-reason-form'
import type {Reason} from '@/types'
export function EditReasonForm({reason,onSaved}:{reason:Reason;onSaved:(key:string)=>void}) {
  return <FlexibleReasonForm reason={reason} onDone={onSaved}/>
}
