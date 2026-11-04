import {lazy}from'react';import{Brain}from'lucide-react';
import './style.css';
const Workspace=lazy(()=>import('./App'));
// Standalone workspace route. Patient context import remains disabled until CARE permissions are mapped.
const manifest={plugin:'second_brain',routes:{'/second-brain':()=> <Workspace/>},extends:[],components:{},userNavItems:[{url:'second-brain',name:'Second Brain',icon:<Brain/>}],devices:[]}as const;
export default manifest;
