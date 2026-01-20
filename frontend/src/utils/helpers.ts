export const debounce = <F extends (...args: any[]) => any>(func: F, wait: number): F => {
  let timeout: number | null = null
  
  return function(...args: Parameters<F>): ReturnType<F> | void {
    if (timeout) clearTimeout(timeout)
    
    timeout = window.setTimeout(() => {
      func(...args)
    }, wait)
  } as F
}

export const throttle = <F extends (...args: any[]) => any>(func: F, limit: number): F => {
  let lastFunc: ReturnType<typeof setTimeout> | null = null
  let lastRan: number = 0
  
  return function(...args: Parameters<F>): ReturnType<F> | void {
    if (!lastRan) {
      func(...args)
      lastRan = Date.now()
    } else {
      if (lastFunc) clearTimeout(lastFunc)
      
      lastFunc = setTimeout(() => {
        if ((Date.now() - lastRan) >= limit) {
          func(...args)
          lastRan = Date.now()
        }
      }, limit - (Date.now() - lastRan))
    }
  } as F
}

export const capitalize = (str: string): string => {
  return str.charAt(0).toUpperCase() + str.slice(1)
}

export const isEmpty = (obj: any): boolean => {
  return Object.keys(obj).length === 0
}
